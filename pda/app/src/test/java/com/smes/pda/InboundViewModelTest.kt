package com.smes.pda

import com.smes.pda.data.model.ApiResult
import com.smes.pda.data.model.ReceiptDetailResponse
import com.smes.pda.data.model.ReceiptScanResponse
import com.smes.pda.data.repository.ReceiptRepository
import com.smes.pda.ui.viewmodel.InboundViewModel
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class InboundViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private val receiptRepository = mockk<ReceiptRepository>()
    private lateinit var viewModel: InboundViewModel

    @Before
    fun setup() {
        Dispatchers.setMain(testDispatcher)
        viewModel = InboundViewModel(receiptRepository)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    // ── initReceipt ──

    @Test
    fun `initReceipt成功_设置activeReceiptId`() = runTest(testDispatcher) {
        val detail = ReceiptDetailResponse(id = 100, type = "inbound", operator = "张三")
        coEvery { receiptRepository.createReceipt("张三", "inbound") } returns ApiResult.Success(detail)

        viewModel.initReceipt("张三")
        advanceUntilIdle()

        with(viewModel.uiState.value) {
            assertEquals(100, activeReceiptId)
            assertEquals("张三", operator)
            assertEquals(false, isLoading)
            assertNull(error)
        }
    }

    @Test
    fun `initReceipt失败_设置错误`() = runTest(testDispatcher) {
        coEvery { receiptRepository.createReceipt(any(), any()) } returns ApiResult.Error("创建入库单失败")

        viewModel.initReceipt("李四")
        advanceUntilIdle()

        with(viewModel.uiState.value) {
            assertNull(activeReceiptId)
            assertEquals("创建入库单失败", error)
            assertEquals(false, isLoading)
        }
    }

    @Test
    fun `initReceipt_loading状态变化`() = runTest(testDispatcher) {
        coEvery { receiptRepository.createReceipt(any(), any()) } returns ApiResult.Success(
            ReceiptDetailResponse(id = 1)
        )

        assertEquals(false, viewModel.uiState.value.isLoading)

        viewModel.initReceipt("王五")
        advanceUntilIdle()
        assertEquals(false, viewModel.uiState.value.isLoading)
    }

    // ── scanBarcode ──

    @Test
    fun `scanBarcode成功_更新扫描记录`() = runTest(testDispatcher) {
        coEvery { receiptRepository.createReceipt(any(), any()) } returns ApiResult.Success(
            ReceiptDetailResponse(id = 50)
        )
        viewModel.initReceipt("赵六")
        advanceUntilIdle()

        val scanResult = ReceiptScanResponse(
            id = 1,
            status = "ok",
            action = "add",
            inventoryPalletId = 200,
            barcode = "BARCODE001",
            materialName = "物料A",
            qty = 100
        )
        coEvery {
            receiptRepository.scanInbound(50, "BARCODE001", "赵六")
        } returns ApiResult.Success(scanResult)

        viewModel.scanBarcode("BARCODE001")
        advanceUntilIdle()

        with(viewModel.uiState.value) {
            assertNotNull(lastScanResult)
            assertEquals("BARCODE001", lastScanResult?.barcode)
            assertEquals(1, scanHistory.size)
            assertEquals("BARCODE001", scanHistory[0].barcode)
            assertEquals(false, isLoading)
            assertNull(error)
        }
    }

    @Test
    fun `scanBarcode无activeReceiptId_不调用API`() = runTest(testDispatcher) {
        viewModel.scanBarcode("SOME_BARCODE")
        advanceUntilIdle()

        coVerify(inverse = true) {
            receiptRepository.scanInbound(any(), any(), any())
        }
        assertEquals(0, viewModel.uiState.value.scanHistory.size)
    }

    @Test
    fun `scanBarcode无operator_不调用API`() = runTest(testDispatcher) {
        coEvery { receiptRepository.createReceipt(any(), any()) } returns ApiResult.Success(
            ReceiptDetailResponse(id = 1)
        )
        viewModel.initReceipt("")
        advanceUntilIdle()

        viewModel.scanBarcode("BARCODE")
        advanceUntilIdle()

        coVerify(inverse = true) {
            receiptRepository.scanInbound(any(), any(), any())
        }
    }

    @Test
    fun `scanBarcodeAPI失败_错误信息设置但history不增加`() = runTest(testDispatcher) {
        coEvery { receiptRepository.createReceipt(any(), any()) } returns ApiResult.Success(
            ReceiptDetailResponse(id = 10)
        )
        viewModel.initReceipt("操作员A")
        advanceUntilIdle()

        coEvery {
            receiptRepository.scanInbound(any(), any(), any())
        } returns ApiResult.Error("条码已存在")

        viewModel.scanBarcode("DUP_BARCODE")
        advanceUntilIdle()

        with(viewModel.uiState.value) {
            assertEquals("条码已存在", error)
            assertEquals(0, scanHistory.size)
            assertNull(lastScanResult)
        }
    }

    // ── scanHistory 连续性 ──

    @Test
    fun `多次扫描_scanHistory累加`() = runTest(testDispatcher) {
        coEvery { receiptRepository.createReceipt(any(), any()) } returns ApiResult.Success(
            ReceiptDetailResponse(id = 5)
        )
        viewModel.initReceipt("操作员B")
        advanceUntilIdle()

        coEvery {
            receiptRepository.scanInbound(5, any(), any())
        } returns ApiResult.Success(
            ReceiptScanResponse(id = 1, status = "ok", barcode = "BARCODE001")
        ) andThen ApiResult.Success(
            ReceiptScanResponse(id = 2, status = "ok", barcode = "BARCODE002")
        )

        viewModel.scanBarcode("BARCODE001")
        advanceUntilIdle()
        assertEquals(1, viewModel.uiState.value.scanHistory.size)

        viewModel.scanBarcode("BARCODE002")
        advanceUntilIdle()
        assertEquals(2, viewModel.uiState.value.scanHistory.size)
    }

    // ── clearLastScan ──

    @Test
    fun `clearLastScan_清除上次扫描结果`() = runTest(testDispatcher) {
        coEvery { receiptRepository.createReceipt(any(), any()) } returns ApiResult.Success(
            ReceiptDetailResponse(id = 1)
        )
        viewModel.initReceipt("OP")
        advanceUntilIdle()

        coEvery { receiptRepository.scanInbound(any(), any(), any()) } returns ApiResult.Success(
            ReceiptScanResponse(id = 1, status = "ok")
        )
        viewModel.scanBarcode("TEST")
        advanceUntilIdle()
        assertNotNull(viewModel.uiState.value.lastScanResult)

        viewModel.clearLastScan()
        assertNull(viewModel.uiState.value.lastScanResult)
    }

    // ── clearError ──

    @Test
    fun `clearError_清除错误`() = runTest(testDispatcher) {
        coEvery { receiptRepository.createReceipt(any(), any()) } returns ApiResult.Error("错误测试")
        viewModel.initReceipt("OP")
        advanceUntilIdle()
        assertNotNull(viewModel.uiState.value.error)

        viewModel.clearError()
        assertNull(viewModel.uiState.value.error)
    }

    // ── 重复扫描 ──

    @Test
    fun `扫描到重复条码_正确处理`() = runTest(testDispatcher) {
        coEvery { receiptRepository.createReceipt(any(), any()) } returns ApiResult.Success(
            ReceiptDetailResponse(id = 1)
        )
        viewModel.initReceipt("OP")
        advanceUntilIdle()

        coEvery { receiptRepository.scanInbound(any(), any(), any()) } returns ApiResult.Success(
            ReceiptScanResponse(
                id = 1,
                status = "duplicate",
                duplicateFlag = true,
                message = "条码已扫描"
            )
        )

        viewModel.scanBarcode("EXISTING_BARCODE")
        advanceUntilIdle()

        with(viewModel.uiState.value) {
            assertEquals(true, lastScanResult?.duplicateFlag)
            assertEquals("条码已扫描", lastScanResult?.message)
            assertEquals(1, scanHistory.size)
        }
    }
}
