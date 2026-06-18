package com.smes.pda.data.api

import com.smes.pda.BuildConfig
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 全局 API 配置。
 *
 * NOTE: HttpService 目前从 SettingsDataStore 读取 URL，
 *       此处仅作为编译期的默认值参考，后续可统一。
 */
@Singleton
class ApiConfig @Inject constructor() {
    companion object {
        val instance: ApiConfig = ApiConfig()
    }

    var baseUrl: String = BuildConfig.DEFAULT_API_URL
    var connectTimeout: Long = 30_000
    var readTimeout: Long = 30_000
}
