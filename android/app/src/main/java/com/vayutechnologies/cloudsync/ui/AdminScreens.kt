package com.vayutechnologies.cloudsync.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.vayutechnologies.cloudsync.data.ApiException
import com.vayutechnologies.cloudsync.data.PortalApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

private data class NamedId(val id: Int, val label: String)
private data class RegionChoice(val code: String, val name: String)

@Composable
fun SettingsScreen(api: PortalApi, onChanged: () -> Unit) {
    val scope = rememberCoroutineScope()
    var loading by remember { mutableStateOf(true) }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var mode by remember { mutableStateOf("profile") }
    var profile by remember { mutableStateOf("") }
    var profiles by remember { mutableStateOf(listOf<String>()) }
    var startUrl by remember { mutableStateOf("") }
    var ssoRegion by remember { mutableStateOf("us-east-1") }
    var ssoAccount by remember { mutableStateOf("") }
    var ssoRole by remember { mutableStateOf("") }
    var testRegion by remember { mutableStateOf("ap-south-1") }
    var regions by remember { mutableStateOf(listOf<RegionChoice>()) }
    var connected by remember { mutableStateOf(false) }
    var userCode by remember { mutableStateOf("") }
    var verifyUri by remember { mutableStateOf("") }
    val context = LocalContext.current

    fun connectionBody() = JSONObject()
        .put("mode", mode)
        .put("profile_name", profile)
        .put("sso_start_url", startUrl.trim())
        .put("sso_region", ssoRegion)
        .put("sso_account_id", ssoAccount.trim())
        .put("sso_role_name", ssoRole.trim())
        .put("region", testRegion)

    fun apply(json: JSONObject) {
        val link = json.optJSONObject("connection") ?: JSONObject()
        mode = link.optString("mode", "profile").ifBlank { "profile" }
        profile = link.optString("profile_name")
        startUrl = link.optString("sso_start_url")
        ssoRegion = link.optString("sso_region").ifBlank { "us-east-1" }
        ssoAccount = link.optString("sso_account_id")
        ssoRole = link.optString("sso_role_name")
        connected = link.optBoolean("sso_connected")
        profiles = json.optJSONArray("profiles").toStrings()
        if (profile.isBlank()) profile = profiles.firstOrNull().orEmpty()
        regions = json.optJSONArray("regions").toRegions()
    }

    LaunchedEffect(Unit) {
        try {
            apply(withContext(Dispatchers.IO) { api.settings() })
        } catch (exception: Exception) {
            error = exception.message ?: "Settings could not be loaded."
        } finally {
            loading = false
        }
    }

    fun run(block: suspend () -> Unit) {
        scope.launch {
            busy = true
            error = null
            message = null
            try {
                block()
            } catch (exception: Exception) {
                error = exception.message ?: "The request failed."
            } finally {
                busy = false
            }
        }
    }

    PageColumn("Settings", "Choose how scans reach AWS, then test the connection.") {
        if (loading) {
            CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
            return@PageColumn
        }
        StatusLine(message, error)
        if (connected) Text("Identity Center session is active.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text("How scans reach AWS", fontWeight = FontWeight.Bold)
        ChoiceRow("Local AWS profile", mode == "profile") { mode = "profile" }
        ChoiceRow("IAM Identity Center", mode == "sso") { mode = "sso" }
        if (mode == "profile") {
            Picker("Profile", profile.ifBlank { "No profile" }, profiles.ifEmpty { listOf("No profiles found") }) {
                profile = it
            }
        } else {
            OutlinedTextField(startUrl, { startUrl = it }, Modifier.fillMaxWidth(), label = { Text("Identity Center start URL") }, singleLine = true)
            RegionPicker("SSO region", ssoRegion, regions) { ssoRegion = it }
            OutlinedTextField(ssoAccount, { if (it.length <= 12 && it.all(Char::isDigit)) ssoAccount = it }, Modifier.fillMaxWidth(), label = { Text("Account ID") }, singleLine = true)
            OutlinedTextField(ssoRole, { ssoRole = it }, Modifier.fillMaxWidth(), label = { Text("Permission set") }, singleLine = true)
        }
        RegionPicker("Test region", testRegion, regions) { testRegion = it }
        Button(
            onClick = {
                run {
                    val saved = withContext(Dispatchers.IO) { api.saveConnection(connectionBody()) }
                    connected = saved.optJSONObject("connection")?.optBoolean("sso_connected") == true
                    message = "AWS connection saved."
                    onChanged()
                }
            },
            enabled = !busy,
            modifier = Modifier.fillMaxWidth().height(48.dp),
            shape = RoundedCornerShape(12.dp),
        ) { Text(if (busy) "Working…" else "Save connection", fontWeight = FontWeight.Bold) }
        OutlinedButton(
            onClick = {
                run {
                    val result = withContext(Dispatchers.IO) { api.testConnection(connectionBody()) }
                    message = "Connected as ${result.optString("account")} in ${result.optString("region")}."
                    onChanged()
                }
            },
            enabled = !busy,
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Test connection") }
        if (mode == "sso") {
            OutlinedButton(
                onClick = {
                    run {
                        val started = withContext(Dispatchers.IO) { api.startSso(connectionBody()) }
                        userCode = started.optString("user_code")
                        verifyUri = started.optString("verification_uri")
                        message = "Approve the code in Identity Center, then confirm below."
                    }
                },
                enabled = !busy,
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Start Identity Center sign-in") }
            if (userCode.isNotBlank()) {
                Text("Code $userCode", fontWeight = FontWeight.Bold)
                if (verifyUri.isNotBlank()) {
                    TextButton(onClick = {
                        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(verifyUri)))
                    }) { Text("Open the sign-in page") }
                }
                OutlinedButton(
                    onClick = {
                        run {
                            val polled = withContext(Dispatchers.IO) { api.pollSso() }
                            when (polled.optString("status")) {
                                "pending" -> message = "Still waiting for approval."
                                "expired" -> error = "That sign-in expired. Start again."
                                else -> {
                                    connected = true
                                    message = "Identity Center is connected."
                                    onChanged()
                                }
                            }
                        }
                    },
                    enabled = !busy,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("I have approved the code") }
            }
        }
    }
}

@Composable
fun ScopeScreen(api: PortalApi, onChanged: () -> Unit) {
    val scope = rememberCoroutineScope()
    var loading by remember { mutableStateOf(true) }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var mode by remember { mutableStateOf("product") }
    var customers by remember { mutableStateOf(listOf<NamedId>()) }
    var environments by remember { mutableStateOf(listOf<NamedId>()) }
    var accounts by remember { mutableStateOf(listOf<JSONObject>()) }
    var regions by remember { mutableStateOf(listOf<RegionChoice>()) }
    var customerId by remember { mutableStateOf(0) }
    var environmentId by remember { mutableStateOf(0) }
    var customerName by remember { mutableStateOf("") }
    var productName by remember { mutableStateOf("") }
    var environmentName by remember { mutableStateOf("") }
    var accountName by remember { mutableStateOf("") }
    var accountId by remember { mutableStateOf("") }
    var roleName by remember { mutableStateOf("") }
    var region by remember { mutableStateOf("ap-south-1") }

    fun apply(json: JSONObject) {
        mode = json.optString("mode", "product")
        customers = json.optJSONArray("customers").toNamed("name")
        environments = json.optJSONArray("environments").toNamed { item ->
            "${item.optString("product")} / ${item.optString("name")}"
        }
        accounts = json.optJSONArray("accounts").toObjects()
        regions = json.optJSONArray("regions").toRegions()
        if (customerId == 0) customerId = customers.firstOrNull()?.id ?: 0
        if (environmentId == 0) environmentId = environments.firstOrNull()?.id ?: 0
    }

    LaunchedEffect(Unit) {
        try {
            apply(withContext(Dispatchers.IO) { api.scope() })
        } catch (exception: Exception) {
            error = exception.message ?: "Accounts could not be loaded."
        } finally {
            loading = false
        }
    }

    PageColumn("AWS accounts", "Add the account scans should read. A role is needed only when this connection must assume into that account.") {
        if (loading) {
            CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
            return@PageColumn
        }
        StatusLine(message, error)
        if (accounts.isEmpty()) Text("No accounts yet.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        accounts.forEach { account ->
            Card(shape = RoundedCornerShape(16.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(account.optString("name"), fontWeight = FontWeight.Bold)
                    Text(
                        "${account.optString("account_id")} · ${account.optString("region")} · ${account.optString("role_name").ifBlank { "Connected identity" }}",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    TextButton(
                        onClick = {
                            scope.launch {
                                busy = true
                                error = null
                                try {
                                    apply(withContext(Dispatchers.IO) { api.deleteScope("accounts", account.optInt("id")) })
                                    message = "Account removed."
                                    onChanged()
                                } catch (exception: Exception) {
                                    error = exception.message
                                } finally {
                                    busy = false
                                }
                            }
                        },
                        enabled = !busy,
                    ) { Text("Remove") }
                }
            }
        }
        Text("Add an account", fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 8.dp))
        if (mode == "msp") {
            if (customers.isNotEmpty()) {
                Picker("Customer", customers.firstOrNull { it.id == customerId }?.label ?: "New customer", customers.map { it.label }) { label ->
                    customerId = customers.firstOrNull { it.label == label }?.id ?: 0
                }
            }
            OutlinedTextField(customerName, { customerName = it }, Modifier.fillMaxWidth(), label = { Text("New customer name") }, singleLine = true)
        } else {
            if (environments.isNotEmpty()) {
                Picker(
                    "Environment",
                    environments.firstOrNull { it.id == environmentId }?.label ?: "New environment",
                    environments.map { it.label },
                ) { label ->
                    environmentId = environments.firstOrNull { it.label == label }?.id ?: 0
                }
            }
            OutlinedTextField(productName, { productName = it }, Modifier.fillMaxWidth(), label = { Text("Product name, if new") }, singleLine = true)
            OutlinedTextField(environmentName, { environmentName = it }, Modifier.fillMaxWidth(), label = { Text("Environment name, if new") }, singleLine = true)
        }
        OutlinedTextField(accountName, { accountName = it }, Modifier.fillMaxWidth(), label = { Text("Account name") }, singleLine = true)
        OutlinedTextField(
            accountId,
            { if (it.length <= 12 && it.all(Char::isDigit)) accountId = it },
            Modifier.fillMaxWidth(),
            label = { Text("Account ID") },
            singleLine = true,
        )
        OutlinedTextField(roleName, { roleName = it }, Modifier.fillMaxWidth(), label = { Text("Role to assume") }, singleLine = true, supportingText = { Text("Leave blank to scan the connected identity.") })
        RegionPicker("Home region", region, regions) { region = it }
        Button(
            onClick = {
                scope.launch {
                    busy = true
                    error = null
                    message = null
                    try {
                        val body = JSONObject()
                            .put("name", accountName.trim())
                            .put("account_id", accountId.trim())
                            .put("role_name", roleName.trim())
                            .put("region", region)
                            .put("customer_id", if (customerName.isBlank()) customerId else 0)
                            .put("customer_name", customerName.trim())
                            .put("environment_id", if (environmentName.isBlank() && productName.isBlank()) environmentId else 0)
                            .put("product_name", productName.trim())
                            .put("environment_name", environmentName.trim())
                        apply(withContext(Dispatchers.IO) { api.addAccount(body) })
                        accountName = ""
                        accountId = ""
                        roleName = ""
                        message = "Account added."
                        onChanged()
                    } catch (exception: Exception) {
                        error = exception.message ?: "The account could not be added."
                    } finally {
                        busy = false
                    }
                }
            },
            enabled = !busy && accountName.isNotBlank() && accountId.length == 12,
            modifier = Modifier.fillMaxWidth().height(48.dp),
            shape = RoundedCornerShape(12.dp),
        ) { Text(if (busy) "Saving…" else "Add account", fontWeight = FontWeight.Bold) }
    }
}

@Composable
fun PeopleScreen(api: PortalApi) {
    val scope = rememberCoroutineScope()
    var loading by remember { mutableStateOf(true) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    var people by remember { mutableStateOf(listOf<JSONObject>()) }
    var username by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var role by remember { mutableStateOf("viewer") }

    suspend fun reload() {
        people = api.people().optJSONArray("people").toObjects()
    }

    LaunchedEffect(Unit) {
        try {
            withContext(Dispatchers.IO) { reload() }
        } catch (exception: Exception) {
            error = exception.message
        } finally {
            loading = false
        }
    }

    PageColumn("People", "Local accounts sign in with a password and an authenticator.") {
        if (loading) {
            CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
            return@PageColumn
        }
        StatusLine(message, error)
        people.forEach { person ->
            Column(Modifier.padding(vertical = 6.dp)) {
                Text(person.optString("username"), fontWeight = FontWeight.SemiBold)
                Text(
                    "${person.optString("email")} · ${person.optString("role")} · ${if (person.optBoolean("active")) "Active" else "Disabled"} · ${if (person.optBoolean("mfa")) "Authenticator set" else "Authenticator not set"}",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outline)
        }
        Text("Add a person", fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 8.dp))
        OutlinedTextField(username, { username = it }, Modifier.fillMaxWidth(), label = { Text("Username") }, singleLine = true)
        OutlinedTextField(email, { email = it }, Modifier.fillMaxWidth(), label = { Text("Email") }, singleLine = true)
        OutlinedTextField(password, { password = it }, Modifier.fillMaxWidth(), label = { Text("Password") }, singleLine = true, visualTransformation = PasswordVisualTransformation())
        Picker("Role", role.replaceFirstChar { it.uppercase() }, listOf("viewer", "admin")) { role = it }
        Button(
            onClick = {
                scope.launch {
                    busy = true
                    error = null
                    try {
                        withContext(Dispatchers.IO) {
                            api.createPerson(
                                JSONObject()
                                    .put("username", username.trim())
                                    .put("email", email.trim())
                                    .put("password", password)
                                    .put("role", role),
                            )
                            reload()
                        }
                        message = "$username can sign in."
                        username = ""
                        email = ""
                        password = ""
                    } catch (exception: Exception) {
                        error = exception.message
                    } finally {
                        busy = false
                    }
                }
            },
            enabled = !busy && username.isNotBlank() && email.contains("@") && password.length >= 8,
            modifier = Modifier.fillMaxWidth().height(48.dp),
            shape = RoundedCornerShape(12.dp),
        ) { Text(if (busy) "Saving…" else "Add person", fontWeight = FontWeight.Bold) }
    }
}

@Composable
fun AuditScreen(api: PortalApi) {
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var logs by remember { mutableStateOf(listOf<JSONObject>()) }
    LaunchedEffect(Unit) {
        try {
            logs = withContext(Dispatchers.IO) { api.audit().optJSONArray("logs").toObjects() }
        } catch (exception: Exception) {
            error = exception.message
        } finally {
            loading = false
        }
    }
    PageColumn("Audit", "Sign-in, scan, and settings activity.") {
        if (loading) CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
        if (!error.isNullOrBlank()) Text(error!!, color = Color(0xFF9B2C2C))
        if (!loading && logs.isEmpty() && error.isNullOrBlank()) Text("No activity yet.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        logs.forEach { log ->
            Column(Modifier.padding(vertical = 6.dp)) {
                Text("${log.optString("when")} · ${log.optString("username")}", style = MaterialTheme.typography.labelMedium)
                Text("${log.optString("action")}  ${log.optString("detail")}", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outline)
        }
    }
}

@Composable
private fun PageColumn(title: String, lede: String, content: @Composable () -> Unit) {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(title, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text(lede, color = MaterialTheme.colorScheme.onSurfaceVariant)
        content()
    }
}

@Composable
private fun StatusLine(message: String?, error: String?) {
    if (!message.isNullOrBlank()) Text(message, color = Color(0xFF1D6B45))
    if (!error.isNullOrBlank()) Text(error, color = Color(0xFF9B2C2C))
}

@Composable
private fun ChoiceRow(label: String, selected: Boolean, onSelect: () -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
        RadioButton(selected = selected, onClick = onSelect)
        Text(label)
    }
}

@Composable
private fun Picker(label: String, value: String, options: List<String>, onSelect: (String) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Column {
        Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelMedium)
        OutlinedButton(onClick = { open = true }, modifier = Modifier.fillMaxWidth()) { Text(value) }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            options.forEach { option ->
                DropdownMenuItem(text = { Text(option) }, onClick = {
                    onSelect(option)
                    open = false
                })
            }
        }
    }
}

@Composable
private fun RegionPicker(label: String, code: String, regions: List<RegionChoice>, onSelect: (String) -> Unit) {
    val choices = regions.ifEmpty { listOf(RegionChoice(code, code)) }
    Picker(label, regionLabel(choices, code), choices.map { regionLabel(choices, it.code) }) { chosen ->
        onSelect(choices.firstOrNull { regionLabel(choices, it.code) == chosen }?.code ?: code)
    }
}

private fun regionLabel(regions: List<RegionChoice>, code: String): String {
    val match = regions.firstOrNull { it.code == code }
    return if (match == null) code else "${match.name} (${match.code})"
}

private fun JSONArray?.toStrings(): List<String> {
    if (this == null) return emptyList()
    return List(length()) { optString(it) }.filter { it.isNotBlank() }
}

private fun JSONArray?.toRegions(): List<RegionChoice> {
    if (this == null) return emptyList()
    return List(length()) { index ->
        val item = optJSONObject(index) ?: JSONObject()
        RegionChoice(item.optString("code"), item.optString("name"))
    }.filter { it.code.isNotBlank() }
}

private fun JSONArray?.toObjects(): List<JSONObject> {
    if (this == null) return emptyList()
    return List(length()) { optJSONObject(it) ?: JSONObject() }
}

private fun JSONArray?.toNamed(label: (JSONObject) -> String): List<NamedId> {
    if (this == null) return emptyList()
    return List(length()) { index ->
        val item = optJSONObject(index) ?: JSONObject()
        NamedId(item.optInt("id"), label(item))
    }
}

private fun JSONArray?.toNamed(field: String) = toNamed { it.optString(field) }
