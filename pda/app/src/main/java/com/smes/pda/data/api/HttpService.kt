package com.smes.pda.data.api

import com.smes.pda.data.local.SettingsDataStore
import io.ktor.client.*
import io.ktor.client.call.*
import io.ktor.client.plugins.*
import io.ktor.client.plugins.contentnegotiation.*
import io.ktor.client.request.*
import io.ktor.client.statement.*
import io.ktor.http.*
import io.ktor.serialization.kotlinx.json.*
import kotlinx.serialization.serializer
import kotlinx.serialization.json.Json
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
open class HttpService @Inject constructor(
    private val settingsDataStore: SettingsDataStore
) {
    val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        coerceInputValues = true
    }

    val client = HttpClient {
        install(ContentNegotiation) {
            json(this@HttpService.json)
        }
        install(HttpTimeout) {
            requestTimeoutMillis = 30_000
            connectTimeoutMillis = 15_000
            socketTimeoutMillis = 30_000
        }
        defaultRequest {
            contentType(ContentType.Application.Json)
        }
    }

    /** Build the full API URL. e.g. baseUrl=http://host/api, path=/auth/login → http://host/api/auth/login */
    suspend fun buildUrl(path: String): String {
        val base = settingsDataStore.getApiUrl().trimEnd('/')
        val cleanPath = path.trimStart('/')
        return "$base/$cleanPath"
    }

    /** Add Authorization header if token is available */
    suspend fun HttpRequestBuilder.withAuth() {
        val token = settingsDataStore.getAuthToken()
        if (token != null) {
            bearerAuth(token)
        }
    }

    /**
     * Low-level execute a GET request.
     * Override this in tests to avoid real HTTP calls.
     */
    open suspend fun executeGet(path: String): String {
        val url = buildUrl(path)
        val response = client.get(url) { withAuth() }
        if (!response.status.isSuccess()) {
            throw HttpException(response.status.value, response.bodyAsText())
        }
        return response.bodyAsText()
    }

    /**
     * Low-level execute a POST request with a JSON body string.
     * Override this in tests to avoid real HTTP calls.
     */
    open suspend fun executePost(path: String, bodyJson: String): String {
        val url = buildUrl(path)
        val response = client.post(url) {
            withAuth()
            setBody(bodyJson)
        }
        if (!response.status.isSuccess()) {
            throw HttpException(response.status.value, response.bodyAsText())
        }
        return response.bodyAsText()
    }

    /**
     * Low-level execute a POST request without body.
     * Override this in tests to avoid real HTTP calls.
     */
    open suspend fun executePostEmpty(path: String): String {
        val url = buildUrl(path)
        val response = client.post(url) { withAuth() }
        if (!response.status.isSuccess()) {
            throw HttpException(response.status.value, response.bodyAsText())
        }
        return response.bodyAsText()
    }

    /**
     * Low-level execute a PUT request with a JSON body string.
     * Override this in tests to avoid real HTTP calls.
     */
    open suspend fun executePut(path: String, bodyJson: String): String {
        val url = buildUrl(path)
        val response = client.put(url) {
            withAuth()
            setBody(bodyJson)
        }
        if (!response.status.isSuccess()) {
            throw HttpException(response.status.value, response.bodyAsText())
        }
        return response.bodyAsText()
    }

    /** GET request, returns deserialized body */
    suspend inline fun <reified T> get(path: String): T {
        val raw = executeGet(path)
        return json.decodeFromString(serializer<T>(), raw)
    }

    /** POST request with body, returns deserialized response */
    suspend inline fun <reified T, reified R> post(path: String, body: T): R {
        val bodyJson = json.encodeToString(serializer<T>(), body)
        val raw = executePost(path, bodyJson)
        return json.decodeFromString(serializer<R>(), raw)
    }

    /** POST request without request body */
    suspend inline fun <reified T> postEmpty(path: String): T {
        val raw = executePostEmpty(path)
        return json.decodeFromString(serializer<T>(), raw)
    }

    /** PUT request with body */
    suspend inline fun <reified T, reified R> put(path: String, body: T): R {
        val bodyJson = json.encodeToString(serializer<T>(), body)
        val raw = executePut(path, bodyJson)
        return json.decodeFromString(serializer<R>(), raw)
    }
}

class HttpException(val statusCode: Int, val responseBody: String) :
    Exception("HTTP $statusCode: $responseBody")
