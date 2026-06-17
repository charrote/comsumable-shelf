package com.smes.pda.data.api

import javax.inject.Inject
import javax.inject.Singleton

@Singleton
open class ApiService @Inject constructor(
    private val authInterceptor: AuthInterceptor
) {
    // API methods will be implemented with Ktor client
    // Placeholder for compilation
}
