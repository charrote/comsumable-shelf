package com.smes.pda.data.api

import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ApiConfig @Inject constructor() {
    companion object {
        val instance: ApiConfig = ApiConfig()
    }

    var baseUrl: String = "http://101.34.63.68/api"
    var connectTimeout: Long = 30_000
    var readTimeout: Long = 30_000
}
