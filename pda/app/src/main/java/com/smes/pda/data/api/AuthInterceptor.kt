package com.smes.pda.data.api

import android.content.Context
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
open class AuthInterceptor @Inject constructor(
    private val context: Context
) {
    open fun getToken(): String? = null

    open fun saveToken(token: String) {}

    open fun clearToken() {}
}
