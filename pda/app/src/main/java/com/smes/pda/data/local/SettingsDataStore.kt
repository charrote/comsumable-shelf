package com.smes.pda.data.local

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.smes.pda.BuildConfig
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore by preferencesDataStore(name = "pda_settings")

@Singleton
class SettingsDataStore @Inject constructor(
    @ApplicationContext private val context: Context
) {
    companion object {
        private val KEY_API_URL = stringPreferencesKey("api_url")
        private val KEY_AUTH_TOKEN = stringPreferencesKey("auth_token")
        private const val DEFAULT_API_URL = BuildConfig.DEFAULT_API_URL
    }

    /** Observe API URL changes as a Flow */
    val apiUrlFlow: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[KEY_API_URL] ?: DEFAULT_API_URL
    }

    /** Get current API URL (suspending) */
    suspend fun getApiUrl(): String {
        return context.dataStore.data.first()[KEY_API_URL] ?: DEFAULT_API_URL
    }

    /** Save a new API URL */
    suspend fun saveApiUrl(url: String) {
        context.dataStore.edit { prefs ->
            prefs[KEY_API_URL] = url
        }
    }

    /** Observe auth token changes */
    val authTokenFlow: Flow<String?> = context.dataStore.data.map { prefs ->
        prefs[KEY_AUTH_TOKEN]
    }

    /** Get current auth token */
    suspend fun getAuthToken(): String? {
        return context.dataStore.data.first()[KEY_AUTH_TOKEN]
    }

    /** Save auth token */
    suspend fun saveAuthToken(token: String) {
        context.dataStore.edit { prefs ->
            prefs[KEY_AUTH_TOKEN] = token
        }
    }

    /** Clear auth token (logout) */
    suspend fun clearAuthToken() {
        context.dataStore.edit { prefs ->
            prefs.remove(KEY_AUTH_TOKEN)
        }
    }
}
