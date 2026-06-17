package com.smes.pda

import com.smes.pda.data.model.*
import com.smes.pda.data.repository.IssueRepository
import com.smes.pda.ui.viewmodel.OutboundViewModel
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
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class OutboundViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private val issueRepository = mockk<IssueRepository>()
    private lateinit var viewModel: OutboundViewModel

    @Before
    fun setup() {
        Dispatchers.setMain(testDispatcher)
        viewModel = OutboundViewModel(issueRepository)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    // ── loadPendingIssues ──

    @Test
    fun `loadPendingIssues成功_更新待出库列表`() = runTest(testDispatcher) {
        val issues = listOf(
            IssueOrderResponse(id = 1, orderNo = "OUT-001", customerName = "客户A", status = "pending"),
            IssueOrderResponse(id = 2, orderNo = "OUT-002", customerName = "客户B", status = "pending")
        )
        coEvery { issueRepository.listIssues(null, "pending") } returns ApiResult.Success(issues)

        viewModel.loadPendingIssues()
        advanceUntilIdle()

        with(viewModel.uiState.value) {
            assertEquals(2, pendingIssues.size)
            assertEquals("OUT-001", pendingIssues[0].orderNo)
            assertEquals("客户B", pendingIssues[1].customerName)
            assertEquals(false, isLoading)
            assertNull(error)
        }
    }

    @Test
    fun `loadPendingIssues空列表`() = runTest(testDispatcher) {
        coEvery { issueRepository.listIssues(any(), any()) } returns ApiResult.Success(emptyList())

        viewModel.loadPendingIssues()
        advanceUntilIdle()

        assertTrue(viewModel.uiState.value.pendingIssues.isEmpty())
    }

    @Test
    fun `loadPendingIssues失败_设置错误`() = runTest(testDispatcher) {
        coEvery { issueRepository.listIssues(any(), any()) } returns ApiResult.Error("获取出库单失败")

        viewModel.loadPendingIssues()
        advanceUntilIdle()

        with(viewModel.uiState.value) {
            assertEquals("获取出库单失败", error)
            assertEquals(0, pendingIssues.size)
            assertEquals(false, isLoading)
        }
    }

    @Test
    fun `loadPendingIssues支持按客户筛选`() = runTest(testDispatcher) {
        coEvery { issueRepository.listIssues(5, "pending") } returns ApiResult.Success(
            listOf(IssueOrderResponse(id = 1))
        )

        viewModel.loadPendingIssues(customerId = 5)
        advanceUntilIdle()

        coVerify { issueRepository.listIssues(5, "pending") }
        assertEquals(1, viewModel.uiState.value.pendingIssues.size)
    }

    // ── selectIssue ──

    @Test
    fun `selectIssue成功_设置选中出库单`() = runTest(testDispatcher) {
        val detail = IssueOrderResponse(
            id = 10,
            orderNo = "OUT-010",
            materialName = "物料X",
            requiredQty = 50
        )
        coEvery { issueRepository.getIssueDetail(10) } returns ApiResult.Success(detail)

        viewModel.selectIssue(10)
        advanceUntilIdle()

        with(viewModel.uiState.value) {
            assertNotNull(selectedIssue)
            assertEquals(10, selectedIssue?.id)
            assertEquals("物料X", selectedIssue?.materialName)
            assertEquals(50, selectedIssue?.requiredQty)
        }
    }

    @Test
    fun `selectIssue失败_错误处理`() = runTest(testDispatcher) {
        coEvery { issueRepository.getIssueDetail(any()) } returns ApiResult.Error("出库单不存在")

        viewModel.selectIssue(999)
        advanceUntilIdle()

        with(viewModel.uiState.value) {
            assertNull(selectedIssue)
            assertEquals("出库单不存在", error)
        }
    }

    // ── calculate ──

    @Test
    fun `calculate成功_返回计算结果`() = runTest(testDispatcher) {
        coEvery { issueRepository.getIssueDetail(1) } returns ApiResult.Success(
            IssueOrderResponse(id = 1)
        )
        viewModel.selectIssue(1)
        advanceUntilIdle()

        val calcResponse = IssueCalculateResponse(
            orderId = 1,
            palletsSelected = listOf(
                PalletSelection(
                    palletId = 100,
                    barcode = "PLT001",
                    materialName = "物料A",
                    availableQty = 200,
                    pickQty = 50,
                    location = "A-01"
                )
            ),
            shortage = 0
        )
        coEvery { issueRepository.calculate(1, "tail_first") } returns ApiResult.Success(calcResponse)

        viewModel.calculate("tail_first")
        advanceUntilIdle()

        with(viewModel.uiState.value) {
            assertNotNull(calcResult)
            assertEquals(1, calcResult?.palletsSelected?.size)
            assertEquals(100, calcResult?.palletsSelected?.get(0)?.palletId)
            assertEquals(0, calcResult?.shortage)
        }
    }

    @Test
    fun `calculate缺料_shortage大于0`() = runTest(testDispatcher) {
        coEvery { issueRepository.getIssueDetail(1) } returns ApiResult.Success(
            IssueOrderResponse(id = 1)
        )
        viewModel.selectIssue(1)
        advanceUntilIdle()

        val shortageResponse = IssueCalculateResponse(
            orderId = 1,
            palletsSelected = listOf(
                PalletSelection(
                    palletId = 101,
                    barcode = "PLT002",
                    materialName = "物料B",
                    availableQty = 30,
                    pickQty = 30,
                    location = "B-02"
                )
            ),
            shortage = 20
        )
        coEvery { issueRepository.calculate(1, any()) } returns ApiResult.Success(shortageResponse)

        viewModel.calculate()
        advanceUntilIdle()

        assertEquals(20, viewModel.uiState.value.calcResult?.shortage)
    }

    @Test
    fun `calculate未选择出库单_不调用API`() = runTest(testDispatcher) {
        viewModel.calculate()
        advanceUntilIdle()

        coVerify(inverse = true) { issueRepository.calculate(any(), any()) }
    }

    // ── assign ──

    @Test
    fun `assign成功_返回LED指令`() = runTest(testDispatcher) {
        coEvery { issueRepository.getIssueDetail(2) } returns ApiResult.Success(
            IssueOrderResponse(id = 2)
        )
        viewModel.selectIssue(2)
        advanceUntilIdle()

        val assignResponse = IssueAssignResponse(
            orderId = 2,
            ledCommands = listOf(
                LedCommand(palletId = 100, location = "A-01", ledColor = "red", ledAction = "flash")
            )
        )
        coEvery { issueRepository.assign(2) } returns ApiResult.Success(assignResponse)

        viewModel.assign()
        advanceUntilIdle()

        with(viewModel.uiState.value) {
            assertNotNull(assignResult)
            assertEquals(1, assignResult?.ledCommands?.size)
            assertEquals("A-01", assignResult?.ledCommands?.get(0)?.location)
        }
    }

    @Test
    fun `assign未选择出库单_不调用API`() = runTest(testDispatcher) {
        viewModel.assign()
        advanceUntilIdle()

        coVerify(inverse = true) { issueRepository.assign(any()) }
    }

    // ── confirmPick ──

    @Test
    fun `confirmPick成功_确认拣货`() = runTest(testDispatcher) {
        coEvery { issueRepository.getIssueDetail(3) } returns ApiResult.Success(
            IssueOrderResponse(id = 3)
        )
        viewModel.selectIssue(3)
        advanceUntilIdle()
        viewModel.setOperator("拣货员A")

        val confirmResponse = IssueConfirmPickResponse(
            status = "completed",
            pickedQty = 50,
            allPicked = true
        )
        coEvery {
            issueRepository.confirmPick(3, "BARCODE003", 101, "拣货员A")
        } returns ApiResult.Success(confirmResponse)

        viewModel.confirmPick("BARCODE003", 101)
        advanceUntilIdle()

        with(viewModel.uiState.value) {
            assertNotNull(confirmResult)
            assertEquals("completed", confirmResult?.status)
            assertEquals(true, confirmResult?.allPicked)
        }
    }

    @Test
    fun `confirmPick未全部拣完_allPicked为false`() = runTest(testDispatcher) {
        coEvery { issueRepository.getIssueDetail(4) } returns ApiResult.Success(
            IssueOrderResponse(id = 4)
        )
        viewModel.selectIssue(4)
        advanceUntilIdle()
        viewModel.setOperator("拣货员B")

        val partialResponse = IssueConfirmPickResponse(
            status = "partial",
            pickedQty = 10,
            allPicked = false
        )
        coEvery {
            issueRepository.confirmPick(any(), any(), any(), any())
        } returns ApiResult.Success(partialResponse)

        viewModel.confirmPick("BARCODE004", 102)
        advanceUntilIdle()

        assertEquals(false, viewModel.uiState.value.confirmResult?.allPicked)
        assertEquals(10, viewModel.uiState.value.confirmResult?.pickedQty)
    }

    @Test
    fun `confirmPick无operator_不调用API`() = runTest(testDispatcher) {
        coEvery { issueRepository.getIssueDetail(5) } returns ApiResult.Success(
            IssueOrderResponse(id = 5)
        )
        viewModel.selectIssue(5)
        advanceUntilIdle()

        viewModel.confirmPick("BARCODE", 100)
        advanceUntilIdle()

        coVerify(inverse = true) { issueRepository.confirmPick(any(), any(), any(), any()) }
    }

    // ── setOperator ──

    @Test
    fun `setOperator更新操作员`() = runTest(testDispatcher) {
        assertEquals("", viewModel.uiState.value.operator)

        viewModel.setOperator("操作员C")
        assertEquals("操作员C", viewModel.uiState.value.operator)
    }

    // ── clearError ──

    @Test
    fun `clearError清除错误`() = runTest(testDispatcher) {
        coEvery { issueRepository.listIssues(any(), any()) } returns ApiResult.Error("系统错误")
        viewModel.loadPendingIssues()
        advanceUntilIdle()
        assertNotNull(viewModel.uiState.value.error)

        viewModel.clearError()
        assertNull(viewModel.uiState.value.error)
    }

    // ── 完整业务流程 ──

    @Test
    fun `完整出库流程_加载_选择_计算_分配_确认`() = runTest(testDispatcher) {
        coEvery { issueRepository.listIssues(any(), any()) } returns ApiResult.Success(
            listOf(IssueOrderResponse(id = 100, orderNo = "OUT-100"))
        )
        viewModel.loadPendingIssues()
        advanceUntilIdle()
        assertEquals(1, viewModel.uiState.value.pendingIssues.size)

        coEvery { issueRepository.getIssueDetail(100) } returns ApiResult.Success(
            IssueOrderResponse(
                id = 100,
                orderNo = "OUT-100",
                materialName = "连接器",
                requiredQty = 500
            )
        )
        viewModel.selectIssue(100)
        advanceUntilIdle()
        assertEquals("连接器", viewModel.uiState.value.selectedIssue?.materialName)

        val calcRes = IssueCalculateResponse(
            orderId = 100,
            palletsSelected = listOf(
                PalletSelection(
                    palletId = 200,
                    barcode = "PLT200",
                    materialName = "连接器",
                    availableQty = 500,
                    pickQty = 500,
                    location = "C-03"
                )
            )
        )
        coEvery { issueRepository.calculate(100, any()) } returns ApiResult.Success(calcRes)
        viewModel.calculate()
        advanceUntilIdle()
        assertEquals(1, viewModel.uiState.value.calcResult?.palletsSelected?.size)

        val assignRes = IssueAssignResponse(
            orderId = 100,
            ledCommands = listOf(
                LedCommand(
                    palletId = 200,
                    location = "C-03",
                    ledColor = "red",
                    ledAction = "flash"
                )
            )
        )
        coEvery { issueRepository.assign(100) } returns ApiResult.Success(assignRes)
        viewModel.assign()
        advanceUntilIdle()
        assertEquals(
            "C-03",
            viewModel.uiState.value.assignResult?.ledCommands?.get(0)?.location
        )

        viewModel.setOperator("拣货员D")
        val confirmRes = IssueConfirmPickResponse(
            status = "completed",
            pickedQty = 500,
            allPicked = true
        )
        coEvery {
            issueRepository.confirmPick(100, "PLT200", 200, "拣货员D")
        } returns ApiResult.Success(confirmRes)
        viewModel.confirmPick("PLT200", 200)
        advanceUntilIdle()
        assertEquals(true, viewModel.uiState.value.confirmResult?.allPicked)
    }
}
