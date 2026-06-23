"""Barcode definition API routes.

条码定义管理 — 用于对固定条码格式的标签进行分段解析，
快速识别物料主数据并填入收料扫码对应字段。
"""

import logging
from typing import List
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)

from app.schemas import (
    BarcodeDefinitionCreate,
    BarcodeDefinitionUpdate,
    BarcodeDefinitionResponse,
    BarcodeDefinitionSegmentSchema,
    BarcodePreviewRequest,
    BarcodeDefPreviewResponse,
    BarcodePreviewSegment,
    BarcodeTestRequest,
    BarcodeTestResponse,
    BarcodeTestSegmentResult,
)
from app.utils.database import get_db
from app.models import BarcodeDefinition, BarcodeDefinitionSegment

router = APIRouter(prefix="/barcode-definitions", tags=["Barcode Definition"])

# ── 可用字段映射列表（供前端下拉使用） ──
AVAILABLE_FIELD_MAPPINGS = [
    # 物料基础数据字段
    {"field": "material_code", "label": "物料编码", "source": "material_master"},
    {"field": "material_name", "label": "物料名称", "source": "material_master"},
    {"field": "spec", "label": "规格型号", "source": "material_master"},
    {"field": "unit", "label": "单位", "source": "material_master"},
    {"field": "qty_per_pallet", "label": "每盘数量", "source": "material_master"},
    # 收料主字段
    {"field": "quantity", "label": "数量", "source": "receipt"},
    {"field": "batch_no", "label": "批次号", "source": "receipt"},
    {"field": "date_code", "label": "生产日期/周期代码", "source": "receipt"},
    {"field": "customer_material_code", "label": "客户物料编码", "source": "receipt"},
]


@router.get("/field-mappings")
async def get_available_field_mappings():
    """获取可用的字段映射列表。"""
    return AVAILABLE_FIELD_MAPPINGS


@router.post("/preview", response_model=BarcodeDefPreviewResponse)
async def preview_barcode_split(
    data: BarcodePreviewRequest,
):
    """预览条码拆分结果（无需保存，直接根据分隔符拆分）。"""
    barcode = data.sample_barcode.strip()
    delimiter = data.delimiter.strip()

    if not barcode:
        raise HTTPException(status_code=400, detail="样例条码不能为空")
    if not delimiter:
        raise HTTPException(status_code=400, detail="分隔符不能为空")

    segments = barcode.split(delimiter)
    result = [
        BarcodePreviewSegment(segment_index=i, value=s.strip())
        for i, s in enumerate(segments)
        if s.strip()
    ]

    return BarcodeDefPreviewResponse(
        segments=result,
        segment_count=len(result),
    )


@router.post("/test", response_model=BarcodeTestResponse)
async def test_barcode_definition(
    data: BarcodeTestRequest,
    db: AsyncSession = Depends(get_db),
):
    """用指定的条码定义解析一个实际条码。"""
    # 查询定义
    result = await db.execute(
        select(BarcodeDefinition).where(BarcodeDefinition.id == data.definition_id)
    )
    definition = result.scalar_one_or_none()
    if not definition:
        raise HTTPException(status_code=404, detail="条码定义不存在")

    # 查询段定义
    seg_result = await db.execute(
        select(BarcodeDefinitionSegment)
        .where(BarcodeDefinitionSegment.definition_id == definition.id)
        .order_by(BarcodeDefinitionSegment.segment_index)
    )
    segments = seg_result.scalars().all()

    if not segments:
        return BarcodeTestResponse(
            definition_id=definition.id,
            definition_name=definition.name,
            delimiter=definition.delimiter,
            barcode=data.barcode,
            matched=False,
            segments=[],
            message="该条码定义没有配置分段",
        )

    # 按分隔符拆分
    parts = data.barcode.strip().split(definition.delimiter)
    parts = [p.strip() for p in parts if p.strip()]

    if len(parts) != len(segments):
        return BarcodeTestResponse(
            definition_id=definition.id,
            definition_name=definition.name,
            delimiter=definition.delimiter,
            barcode=data.barcode,
            matched=False,
            segments=[],
            message=f"条码段数({len(parts)})与定义段数({len(segments)})不匹配",
        )

    seg_results = []
    for seg, part in zip(segments, parts):
        seg_results.append(BarcodeTestSegmentResult(
            segment_index=seg.segment_index,
            value=part,
            field_mapping=seg.field_mapping or "",
            field_label=seg.field_label or ("忽略" if not seg.field_mapping else seg.field_label),
        ))

    return BarcodeTestResponse(
        definition_id=definition.id,
        definition_name=definition.name,
        delimiter=definition.delimiter,
        barcode=data.barcode,
        matched=True,
        segments=seg_results,
        message="条码匹配成功",
    )


@router.get("", response_model=List[BarcodeDefinitionResponse])
async def list_barcode_definitions(
    db: AsyncSession = Depends(get_db),
):
    """获取所有条码定义列表。"""
    try:
        result = await db.execute(
            select(BarcodeDefinition)
            .options(selectinload(BarcodeDefinition.segments))
            .order_by(BarcodeDefinition.created_at.desc())
        )
        definitions = result.scalars().all()
        return [_definition_to_response(d) for d in definitions]
    except Exception as e:
        logger.error(f"查询条码定义列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询条码定义失败：数据库表可能尚未创建，请重启后端服务。错误: {e}")


@router.get("/{definition_id}", response_model=BarcodeDefinitionResponse)
async def get_barcode_definition(
    definition_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单个条码定义详情。"""
    try:
        result = await db.execute(
            select(BarcodeDefinition)
            .options(selectinload(BarcodeDefinition.segments))
            .where(BarcodeDefinition.id == definition_id)
        )
        definition = result.scalar_one_or_none()
        if not definition:
            raise HTTPException(status_code=404, detail="条码定义不存在")
        return _definition_to_response(definition)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询条码定义 {definition_id} 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询条码定义失败: {e}")


async def _check_duplicate_definition(
    db: AsyncSession,
    delimiter: str,
    segment_count: int,
    exclude_id: int = None,
):
    """检查是否存在相同（分隔符, 段数）的已启用定义。

    Args:
        db: 数据库会话
        delimiter: 分隔符
        segment_count: 段数量
        exclude_id: 排除的ID（用于更新时排除自身）

    Raises:
        HTTPException: 如果存在重复定义
    """
    query = select(BarcodeDefinition).where(
        BarcodeDefinition.is_active == 1,
        BarcodeDefinition.delimiter == delimiter,
    )
    if exclude_id:
        query = query.where(BarcodeDefinition.id != exclude_id)

    result = await db.execute(query)
    existing = result.scalars().all()

    for ex in existing:
        # 查询已有定义的段数
        seg_result = await db.execute(
            select(BarcodeDefinitionSegment)
            .where(BarcodeDefinitionSegment.definition_id == ex.id)
        )
        ex_seg_count = len(seg_result.scalars().all())
        if ex_seg_count == segment_count:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"条码定义「{ex.name}」(ID={ex.id}) 已存在完全相同的匹配规则"
                    f"（分隔符=「{delimiter}」, {segment_count}段），"
                    f"请先禁用或修改该定义"
                ),
            )


@router.post("", response_model=BarcodeDefinitionResponse)
async def create_barcode_definition(
    data: BarcodeDefinitionCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建条码定义。"""
    # 检查重复（分隔符, 段数 不允许重复）
    await _check_duplicate_definition(
        db,
        delimiter=data.delimiter.strip(),
        segment_count=len(data.segments),
    )

    # 创建定义（barcode_length 优先用传入值，否则自动取样例条码长度）
    barcode_length = data.barcode_length or len(data.sample_barcode.strip())
    definition = BarcodeDefinition(
        name=data.name.strip(),
        delimiter=data.delimiter.strip(),
        sample_barcode=data.sample_barcode.strip(),
        barcode_length=barcode_length,
        is_active=1,
    )
    db.add(definition)
    await db.flush()

    # 创建段（field_mapping 为空表示忽略该段）
    for seg in data.segments:
        db_seg = BarcodeDefinitionSegment(
            definition_id=definition.id,
            segment_index=seg.segment_index,
            segment_sample=seg.segment_sample,
            field_mapping=seg.field_mapping or None,  # 空字符串存为 None
            field_label=seg.field_label or None,
        )
        db.add(db_seg)

    await db.commit()
    # 显式加载 segments（传给 response 避免触发 lazy load）
    seg_result = await db.execute(
        select(BarcodeDefinitionSegment)
        .where(BarcodeDefinitionSegment.definition_id == definition.id)
        .order_by(BarcodeDefinitionSegment.segment_index)
    )
    seg_list = list(seg_result.scalars().all())
    return _definition_to_response(definition, segments=seg_list)


@router.put("/{definition_id}", response_model=BarcodeDefinitionResponse)
async def update_barcode_definition(
    definition_id: int,
    data: BarcodeDefinitionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新条码定义。"""
    result = await db.execute(
        select(BarcodeDefinition).where(BarcodeDefinition.id == definition_id)
    )
    definition = result.scalar_one_or_none()
    if not definition:
        raise HTTPException(status_code=404, detail="条码定义不存在")

    # 更新标量字段
    if data.name is not None:
        definition.name = data.name.strip()
    if data.delimiter is not None:
        definition.delimiter = data.delimiter.strip()
    if data.sample_barcode is not None:
        definition.sample_barcode = data.sample_barcode.strip()
    if data.barcode_length is not None:
        definition.barcode_length = data.barcode_length
    elif data.sample_barcode is not None:
        # 只改了样例条码但没改长度 → 自动重算
        definition.barcode_length = len(data.sample_barcode.strip())
    if data.is_active is not None:
        definition.is_active = data.is_active

    # 检查重复（分隔符, 段数 不允许重复）
    effective_delimiter = data.delimiter.strip() if data.delimiter is not None else definition.delimiter
    effective_segments = data.segments if data.segments is not None else None
    if effective_segments is not None:
        await _check_duplicate_definition(
            db,
            delimiter=effective_delimiter,
            segment_count=len(effective_segments),
            exclude_id=definition.id,
        )

    # 更新段（如果提供了）
    if data.segments is not None:
        # 删除旧段
        await db.execute(
            sa_delete(BarcodeDefinitionSegment).where(
                BarcodeDefinitionSegment.definition_id == definition.id
            )
        )
        # 创建新段（field_mapping 为空表示忽略该段）
        for seg in data.segments:
            db_seg = BarcodeDefinitionSegment(
                definition_id=definition.id,
                segment_index=seg.segment_index,
                segment_sample=seg.segment_sample,
                field_mapping=seg.field_mapping or None,
                field_label=seg.field_label or None,
            )
            db.add(db_seg)

    await db.commit()
    # 显式加载 segments（传给 response 避免触发 lazy load）
    seg_result = await db.execute(
        select(BarcodeDefinitionSegment)
        .where(BarcodeDefinitionSegment.definition_id == definition.id)
        .order_by(BarcodeDefinitionSegment.segment_index)
    )
    seg_list = list(seg_result.scalars().all())
    return _definition_to_response(definition, segments=seg_list)


@router.delete("/{definition_id}")
async def delete_barcode_definition(
    definition_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除条码定义。"""
    result = await db.execute(
        select(BarcodeDefinition).where(BarcodeDefinition.id == definition_id)
    )
    definition = result.scalar_one_or_none()
    if not definition:
        raise HTTPException(status_code=404, detail="条码定义不存在")

    await db.delete(definition)
    await db.commit()
    return {"status": "ok", "message": f"条码定义「{definition.name}」已删除"}


# ── 工具函数 ──

async def _get_definition_segments(
    db: AsyncSession, definition_id: int
) -> List[BarcodeDefinitionSegment]:
    """获取条码定义的所有段。"""
    result = await db.execute(
        select(BarcodeDefinitionSegment)
        .where(BarcodeDefinitionSegment.definition_id == definition_id)
        .order_by(BarcodeDefinitionSegment.segment_index)
    )
    return list(result.scalars().all())


def _definition_to_response(definition: BarcodeDefinition, segments: list = None) -> BarcodeDefinitionResponse:
    """将 ORM 模型转换为响应 Schema。

    Args:
        definition: BarcodeDefinition ORM 实例
        segments: Segment 列表（显式传入可避免触发 lazy load）
    """
    seg_list = segments if segments is not None else (definition.segments or [])
    segment_schemas = [
        BarcodeDefinitionSegmentSchema(
            segment_index=s.segment_index,
            segment_sample=s.segment_sample,
            field_mapping=s.field_mapping or "",
            field_label=s.field_label or "",
        )
        for s in seg_list
    ]
    return BarcodeDefinitionResponse(
        id=definition.id,
        name=definition.name,
        delimiter=definition.delimiter,
        sample_barcode=definition.sample_barcode,
        barcode_length=definition.barcode_length or 0,
        is_active=definition.is_active or 1,
        segments=segment_schemas,
        created_at=definition.created_at,
        updated_at=definition.updated_at,
    )


# ── 收料扫码集成工具函数（供 receipt.py 使用） ──

async def parse_barcode_with_definitions(
    db: AsyncSession,
    barcode: str,
) -> tuple:
    """使用启用的条码定义解析条码。

    遍历所有启用的条码定义，尝试匹配并解析。
    如果匹配成功，返回 (definition, extracted_fields_dict)。
    否则返回 (None, None)。

    extracted_fields_dict 的 key 是 field_mapping，value 是解析出的值。
    """
    result = await db.execute(
        select(BarcodeDefinition).where(BarcodeDefinition.is_active == 1)
    )
    definitions = result.scalars().all()

    raw_barcode = barcode.strip()

    for definition in definitions:
        # ── 第 1 关：匹配分隔符 ──
        if definition.delimiter not in raw_barcode:
            continue

        # ── 第 2 关：按分隔符拆分，匹配段数 ──
        seg_result = await db.execute(
            select(BarcodeDefinitionSegment)
            .where(BarcodeDefinitionSegment.definition_id == definition.id)
            .order_by(BarcodeDefinitionSegment.segment_index)
        )
        segments = seg_result.scalars().all()
        if not segments:
            continue

        parts = raw_barcode.split(definition.delimiter)
        parts = [p.strip() for p in parts if p.strip()]

        if len(parts) != len(segments):
            continue

        # 三段全匹配 → 使用该定义解析
        fields = {}
        for seg, part in zip(segments, parts):
            if seg.field_mapping:  # 只提取有映射的段
                fields[seg.field_mapping] = part

        return definition, fields

    return None, None
