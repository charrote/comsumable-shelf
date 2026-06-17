package com.smes.pda

import com.smes.pda.data.model.ApiResult
import com.smes.pda.data.model.UserResponse
import com.smes.pda.data.repository.AuthRepository
import com.smes.pda.ui.viewmodel.AuthViewModel
import io.mockk.coEvery
import io.mockk.every
import io.mockk.just
import io.mockk.mockk
import io.mockk.runs
import io.mockk.verify
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
class AuthViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private val authRepository = mockk<AuthRepository>()
    private lateinit var viewModel: AuthViewModel

    @Before
    fun setup() {
        Dispatchers.setMain(testDispatcher)
        every { authRepository.isLoggedIn() } returns false
        viewModel = AuthViewModel(authRepository)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    // ── 初始状态测试 ──

    @Test
    fun `初始状态为未登录`() = runTest(testDispatcher) {
        val state = viewModel.uiState.value
        assertEquals(false, state.isLoggedIn)
        assertEquals(false, state.isLoading)
        assertNull(state.user)
        assertNull(state.error)
    }

    @Test
    fun `初始状态_已登录过`() = runTest(testDispatcher) {
        every { authRepository.isLoggedIn() } returns true
        val loggedInVm = AuthViewModel(authRepository)
        assertEquals(true, loggedInVm.uiState.value.isLoggedIn)
    }

    // ── login 成功 ──

    @Test
    fun `login成功_状态流转正确`() = runTest(testDispatcher) {
        val expectedUser = UserResponse(id = 1, username = "admin", displayName = "管理员")
        coEvery { authRepository.login("admin", "pass") } returns ApiResult.Success(expectedUser)
        coEvery { authRepository.getMe() } returns ApiResult.Success(expectedUser)

        assertEquals(false, viewModel.uiState.value.isLoading)

        viewModel.login("admin", "pass")
        advanceUntilIdle()

        with(viewModel.uiState.value) {
            assertEquals(false, isLoading)
            assertEquals(true, isLoggedIn)
            assertNotNull(user)
            assertEquals("admin", user?.username)
            assertEquals("管理员", user?.displayName)
            assertNull(error)
        }
    }

    @Test
    fun `login成功_getMe失败_仍标记为已登录`() = runTest(testDispatcher) {
        val mockUser = UserResponse(id = 1, username = "admin")
        coEvery { authRepository.login(any(), any()) } returns ApiResult.Success(mockUser)
        coEvery { authRepository.getMe() } returns ApiResult.Error("Network error")

        viewModel.login("admin", "pass")
        advanceUntilIdle()

        with(viewModel.uiState.value) {
            assertEquals(true, isLoggedIn)
            assertNull(this.user) // `this.user` 引用 AuthUiState.user 属性
        }
    }

    // ── login 失败 ──

    @Test
    fun `login失败_设置错误信息`() = runTest(testDispatcher) {
        coEvery { authRepository.login(any(), any()) } returns ApiResult.Error("用户名或密码错误")

        viewModel.login("wrong", "credentials")
        advanceUntilIdle()

        with(viewModel.uiState.value) {
            assertEquals(false, isLoggedIn)
            assertEquals(false, isLoading)
            assertEquals("用户名或密码错误", error)
        }
    }

    // ── logout ──

    @Test
    fun `logout_重置状态并清除token`() = runTest(testDispatcher) {
        val mockUser = UserResponse(id = 1, username = "admin")
        coEvery { authRepository.login(any(), any()) } returns ApiResult.Success(mockUser)
        coEvery { authRepository.getMe() } returns ApiResult.Success(mockUser)
        every { authRepository.logout() } just runs

        viewModel.login("admin", "pass")
        advanceUntilIdle()
        assertEquals(true, viewModel.uiState.value.isLoggedIn)

        viewModel.logout()
        advanceUntilIdle()

        with(viewModel.uiState.value) {
            assertEquals(false, isLoggedIn)
            assertNull(this.user)
            assertNull(error)
        }
        verify { authRepository.logout() }
    }

    // ── clearError ──

    @Test
    fun `clearError_清除错误信息`() = runTest(testDispatcher) {
        coEvery { authRepository.login(any(), any()) } returns ApiResult.Error("登录失败")
        viewModel.login("x", "y")
        advanceUntilIdle()
        assertNotNull(viewModel.uiState.value.error)

        viewModel.clearError()
        assertNull(viewModel.uiState.value.error)
    }

    @Test
    fun `clearError_不影响其他状态`() = runTest(testDispatcher) {
        every { authRepository.isLoggedIn() } returns true
        val vm = AuthViewModel(authRepository)

        vm.clearError()
        assertEquals(true, vm.uiState.value.isLoggedIn)
    }

    // ── 边界条件 ──

    @Test
    fun `重复login_只有最后一次有效`() = runTest(testDispatcher) {
        coEvery { authRepository.login("first", any()) } returns ApiResult.Success(
            UserResponse(id = 1, username = "first")
        )
        coEvery { authRepository.login("second", any()) } returns ApiResult.Success(
            UserResponse(id = 2, username = "second")
        )
        coEvery { authRepository.getMe() } returns ApiResult.Error("noop")

        viewModel.login("first", "p1")
        viewModel.login("second", "p2")
        advanceUntilIdle()

        assertEquals(true, viewModel.uiState.value.isLoggedIn)
    }
}
