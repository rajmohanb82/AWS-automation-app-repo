package com.vayutechnologies.cloudsync.data

import android.content.Context
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class ApiException(val code: Int, message: String) : Exception(message)

class PortalApi(context: Context) {
    private val prefs = context.getSharedPreferences("cloudsync", Context.MODE_PRIVATE)
    private val http = OkHttpClient.Builder()
        .cookieJar(PrefCookieJar(prefs))
        .followRedirects(false)
        .followSslRedirects(false)
        .connectTimeout(12, TimeUnit.SECONDS)
        .readTimeout(40, TimeUnit.SECONDS)
        .build()

    var server: String
        get() = prefs.getString("server", "http://127.0.0.1:5080")!!.trim().trimEnd('/')
        set(value) {
            prefs.edit().putString("server", value.trim().trimEnd('/')).apply()
        }

    var theme: String
        get() = prefs.getString("theme", "system") ?: "system"
        set(value) {
            prefs.edit().putString("theme", value).apply()
        }

    private var csrf: String
        get() = prefs.getString("csrf", "") ?: ""
        set(value) {
            prefs.edit().putString("csrf", value).apply()
        }

    fun clearSession() {
        prefs.edit().remove("csrf").remove("cookies").apply()
    }

    fun bootstrap(): JSONObject {
        return try {
            call("GET", "/api/mobile/bootstrap", readSeconds = 15, connectSeconds = 6)
        } catch (first: Exception) {
            val fallback = fallbackServer(server) ?: throw first
            val previous = server
            server = fallback
            try {
                call("GET", "/api/mobile/bootstrap", readSeconds = 15, connectSeconds = 6)
            } catch (_: Exception) {
                server = previous
                throw first
            }
        }
    }

    fun login(username: String, password: String): JSONObject {
        return call("POST", "/api/mobile/login", JSONObject().put("username", username).put("password", password))
    }

    fun verify(code: String) = call("POST", "/api/mobile/mfa/verify", JSONObject().put("code", code))

    fun enrollInfo() = call("GET", "/api/mobile/mfa/enroll")

    fun enrollConfirm() = call("POST", "/api/mobile/mfa/enroll", JSONObject())

    fun home() = call("GET", "/api/mobile/home")

    fun report(reportId: String, accountPk: Int, region: String): JSONObject {
        return call(
            "POST",
            "/api/mobile/reports/$reportId",
            JSONObject().put("account_pk", accountPk).put("region", region),
            readSeconds = 180,
            connectSeconds = 20,
        )
    }

    fun reportPdf(reportId: String, accountPk: Int, region: String): ByteArray {
        val body = JSONObject().put("account_pk", accountPk).put("region", region)
        val builder = Request.Builder()
            .url("$server/api/mobile/reports/$reportId/pdf")
            .header("Accept", "application/pdf")
            .post(body.toString().toRequestBody("application/json; charset=utf-8".toMediaType()))
        if (csrf.isNotEmpty()) builder.header("X-CSRF-Token", csrf)
        val client = http.newBuilder()
            .readTimeout(180, TimeUnit.SECONDS)
            .connectTimeout(20, TimeUnit.SECONDS)
            .build()
        client.newCall(builder.build()).execute().use { response ->
            val bytes = response.body?.bytes() ?: ByteArray(0)
            if (!response.isSuccessful) {
                val text = bytes.toString(Charsets.UTF_8)
                val json = if (text.trim().startsWith("{")) JSONObject(text) else JSONObject()
                throw ApiException(response.code, json.optString("error", "The PDF could not be created."))
            }
            if (bytes.size < 5 || bytes.copyOfRange(0, 4).decodeToString() != "%PDF") {
                throw ApiException(response.code, "The report file was empty.")
            }
            return bytes
        }
    }

    fun settings() = call("GET", "/api/mobile/settings")

    fun saveConnection(body: JSONObject) = call("POST", "/api/mobile/settings/aws", body)

    fun testConnection(body: JSONObject) = call("POST", "/api/mobile/aws/test", body, readSeconds = 90)

    fun startSso(body: JSONObject) = call("POST", "/api/mobile/aws/sso/start", body, readSeconds = 90)

    fun pollSso() = call("POST", "/api/mobile/aws/sso/poll", JSONObject(), readSeconds = 90)

    fun scope() = call("GET", "/api/mobile/scope")

    fun addAccount(body: JSONObject) = call("POST", "/api/mobile/scope/accounts", body)

    fun deleteScope(table: String, id: Int) = call(
        "POST",
        "/api/mobile/scope/delete",
        JSONObject().put("table", table).put("id", id),
    )

    fun people() = call("GET", "/api/mobile/people")

    fun createPerson(body: JSONObject) = call("POST", "/api/mobile/people", body)

    fun audit() = call("GET", "/api/mobile/audit")

    fun logout() {
        try {
            call("POST", "/api/mobile/logout", JSONObject())
        } catch (_: Exception) {
        }
        clearSession()
    }

    private fun fallbackServer(current: String): String? {
        if (current.contains("127.0.0.1")) return current.replace("127.0.0.1", "10.0.2.2")
        if (current.contains("localhost")) return current.replace("localhost", "10.0.2.2")
        return null
    }

    private fun call(
        method: String,
        path: String,
        body: JSONObject? = null,
        readSeconds: Long = 40,
        connectSeconds: Long = 12,
    ): JSONObject {
        val builder = Request.Builder()
            .url(server + path)
            .header("Accept", "application/json")
        if (csrf.isNotEmpty()) builder.header("X-CSRF-Token", csrf)
        val jsonType = "application/json; charset=utf-8".toMediaType()
        when {
            body != null -> builder.method(method, body.toString().toRequestBody(jsonType))
            method == "POST" -> builder.post("{}".toRequestBody(jsonType))
            else -> builder.get()
        }
        val client = http.newBuilder()
            .readTimeout(readSeconds, TimeUnit.SECONDS)
            .connectTimeout(connectSeconds, TimeUnit.SECONDS)
            .build()
        client.newCall(builder.build()).execute().use { response ->
            val text = response.body?.string().orEmpty()
            val json = if (text.trim().startsWith("{")) JSONObject(text) else JSONObject()
            if (json.has("csrf")) csrf = json.getString("csrf")
            if (!response.isSuccessful) {
                throw ApiException(response.code, json.optString("error", "The request failed."))
            }
            return json
        }
    }
}

private class PrefCookieJar(private val prefs: android.content.SharedPreferences) : CookieJar {
    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        val kept = load().filterNot { old -> cookies.any { it.name == old.name && it.domain == old.domain } } + cookies
        val array = JSONArray()
        kept.forEach { cookie ->
            array.put(
                JSONObject()
                    .put("name", cookie.name)
                    .put("value", cookie.value)
                    .put("domain", cookie.domain)
                    .put("path", cookie.path)
                    .put("secure", cookie.secure)
                    .put("httpOnly", cookie.httpOnly)
                    .put("hostOnly", cookie.hostOnly)
                    .put("expires", cookie.expiresAt)
            )
        }
        prefs.edit().putString("cookies", array.toString()).apply()
    }

    override fun loadForRequest(url: HttpUrl): List<Cookie> {
        val now = System.currentTimeMillis()
        return load().filter { it.expiresAt > now && it.matches(url) }
    }

    private fun load(): List<Cookie> {
        val raw = prefs.getString("cookies", "[]") ?: "[]"
        val array = JSONArray(raw)
        val cookies = mutableListOf<Cookie>()
        for (index in 0 until array.length()) {
            val item = array.getJSONObject(index)
            val builder = Cookie.Builder()
                .name(item.getString("name"))
                .value(item.getString("value"))
                .path(item.optString("path", "/"))
                .expiresAt(item.optLong("expires", Long.MAX_VALUE))
            if (item.optBoolean("hostOnly")) builder.hostOnlyDomain(item.getString("domain"))
            else builder.domain(item.getString("domain"))
            if (item.optBoolean("secure")) builder.secure()
            if (item.optBoolean("httpOnly")) builder.httpOnly()
            cookies.add(builder.build())
        }
        return cookies
    }
}
