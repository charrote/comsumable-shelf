package com.smes.pda.data.repository

import com.smes.pda.data.model.ApiResult
import com.smes.pda.data.model.UserResponse
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
open class AuthRepository @Inject constructor() {

    open suspend fun login(username: String, password: String): ApiResult<UserResponse> {
        return ApiResult.Error("Not implemented")
    }

    open fun isLoggedIn(): Boolean = false

    open fun logout() {}

    open suspend fun getMe(): ApiResult<UserResponse> {
        return ApiResult.Error("Not implemented")
    }
}
