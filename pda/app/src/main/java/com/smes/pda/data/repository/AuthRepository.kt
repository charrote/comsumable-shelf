package com.smes.pda.data.repository

import com.smes.pda.data.api.HttpException
import com.smes.pda.data.api.HttpService
import com.smes.pda.data.local.SettingsDataStore
import com.smes.pda.data.model.ApiResult
import com.smes.pda.data.model.LoginRequest
import com.smes.pda.data.model.TokenResponse
import com.smes.pda.data.model.UserResponse
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
open class AuthRepository @Inject constructor(
    private val httpService: HttpService,
    private val settingsDataStore: SettingsDataStore
) {
    open suspend fun login(username: String, password: String): ApiResult<UserResponse> {
        return try {
            val tokenResponse: TokenResponse = httpService.post("auth/login", LoginRequest(username, password))
            settingsDataStore.saveAuthToken(tokenResponse.accessToken)
            // Fetch user info
            val me: UserResponse = httpService.get("auth/me")
            ApiResult.Success(me)
        } catch (e: HttpException) {
            ApiResult.Error(e.responseBody, e.statusCode)
        } catch (e: Exception) {
            ApiResult.Error(e.message ?: "登录失败，请检查网络连接")
        }
    }

    open fun isLoggedIn(): Boolean {
        return try {
            kotlinx.coroutines.runBlocking {
                settingsDataStore.getAuthToken() != null
            }
        } catch (e: Exception) {
            false
        }
    }

    open suspend fun logout() {
        settingsDataStore.clearAuthToken()
    }

    open suspend fun getMe(): ApiResult<UserResponse> {
        return try {
            val me: UserResponse = httpService.get("auth/me")
            ApiResult.Success(me)
        } catch (e: HttpException) {
            ApiResult.Error(e.responseBody, e.statusCode)
        } catch (e: Exception) {
            ApiResult.Error(e.message ?: "获取用户信息失败")
        }
    }
}
