package com.vayutechnologies.cloudsync.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.systemGestureExclusion
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.ShoppingCart
import androidx.compose.material.icons.filled.Build
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.zIndex
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import android.content.ActivityNotFoundException
import android.content.Intent
import androidx.core.content.FileProvider
import com.vayutechnologies.cloudsync.R
import com.vayutechnologies.cloudsync.data.ApiException
import com.vayutechnologies.cloudsync.data.PortalApi
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

private data class Point(val label: String, val value: Int, val tone: Color)
private data class Topic(val caption: String, val series: List<Point>)
private data class ScanRow(val whenText: String, val kind: String, val account: String, val region: String, val total: Int, val high: Int, val actor: String)
private data class LogRow(val whenText: String, val person: String, val action: String, val detail: String)
private data class ReportCard(val id: String, val code: String, val title: String, val audience: String, val summary: String)
private data class AccountRef(val id: Int, val name: String, val accountId: String, val region: String)
private data class Bar(val label: String, val value: Double)
private data class ReportSection(
    val title: String,
    val chartTitle: String,
    val money: Boolean,
    val chart: List<Bar>,
    val columns: List<String>,
    val rows: List<List<String>>,
)
private data class ReportDocument(
    val code: String,
    val domain: String,
    val title: String,
    val audience: String,
    val summary: String,
    val subtitle: String,
    val money: Boolean,
    val kpis: List<Pair<String, String>>,
    val chartTitle: String,
    val chart: List<Bar>,
    val notes: List<String>,
    val sections: List<ReportSection>,
)
private data class ReportGroup(val id: String, val label: String, val headline: String, val blurb: String, val reports: List<ReportCard>)
private data class Home(
    val username: String,
    val role: String,
    val org: String,
    val accounts: Int,
    val products: Int,
    val customers: Int,
    val mode: String,
    val aws: String,
    val highOpen: Int,
    val housekeeping: Topic,
    val governance: Topic,
    val cost: Topic,
    val scans: List<ScanRow>,
    val logs: List<LogRow>,
    val accountLines: List<String>,
    val accountRefs: List<AccountRef>,
    val reports: List<ReportGroup>,
)

private fun menuIcon(id: String) = when (id) {
    "dashboard" -> Icons.Filled.Home
    "housekeeping" -> Icons.Filled.Build
    "cost" -> Icons.Filled.ShoppingCart
    "governance" -> Icons.Filled.Lock
    "reports" -> Icons.Filled.List
    "settings" -> Icons.Filled.Settings
    "people" -> Icons.Filled.Person
    else -> Icons.Filled.List
}

@Composable
fun CloudSyncApp(api: PortalApi) {
    val scope = rememberCoroutineScope()
    var darkChoice by remember { mutableStateOf(api.theme) }
    val systemDark = androidx.compose.foundation.isSystemInDarkTheme()
    val dark = when (darkChoice) {
        "dark" -> true
        "light" -> false
        else -> systemDark
    }
    var screen by remember { mutableStateOf("boot") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var home by remember { mutableStateOf<Home?>(null) }
    var enrollPin by remember { mutableStateOf("") }
    var enrollUri by remember { mutableStateOf("") }

    fun setTheme(choice: String) {
        darkChoice = choice
        api.theme = choice
    }

    fun work(block: suspend () -> Unit) {
        scope.launch {
            busy = true
            error = null
            try {
                withContext(Dispatchers.IO) { block() }
            } catch (exception: ApiException) {
                error = exception.message
                if (exception.code == 401 || screen == "boot") screen = "login"
            } catch (exception: Exception) {
                error = exception.message ?: "The console could not be reached."
                if (screen == "boot") screen = "login"
            } finally {
                busy = false
            }
        }
    }

    LaunchedEffect(Unit) {
        work {
            api.bootstrap()
            try {
                home = api.home().toHome()
                screen = "home"
            } catch (exception: ApiException) {
                screen = "login"
                if (exception.code != 401) error = exception.message
            }
        }
    }

    CloudSyncTheme(dark) {
        when (screen) {
            "boot" -> Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                    Text("Opening CloudSync…", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            "login" -> LoginScreen(
                api = api,
                busy = busy,
                error = error,
                theme = darkChoice,
                onTheme = ::setTheme,
                onSubmit = { username, password ->
                    work {
                        val result = api.login(username, password)
                        when (result.optString("step")) {
                            "enroll" -> {
                                val info = api.enrollInfo()
                                enrollPin = info.optString("pin")
                                enrollUri = info.optString("uri")
                                screen = "enroll"
                            }
                            else -> screen = "verify"
                        }
                    }
                },
            )
            "verify" -> VerifyScreen(
                busy = busy,
                error = error,
                theme = darkChoice,
                onTheme = ::setTheme,
                onSubmit = { code ->
                    work {
                        api.verify(code)
                        home = api.home().toHome()
                        screen = "home"
                    }
                },
                onBack = { screen = "login" },
            )
            "enroll" -> EnrollScreen(
                pin = enrollPin,
                uri = enrollUri,
                busy = busy,
                error = error,
                onConfirm = {
                    work {
                        api.enrollConfirm()
                        home = api.home().toHome()
                        screen = "home"
                    }
                },
                onBack = { screen = "login" },
            )
            else -> home?.let { data ->
                ConsoleScreen(
                    api = api,
                    home = data,
                    busy = busy,
                    theme = darkChoice,
                    onTheme = ::setTheme,
                    onRefresh = {
                        work { home = api.home().toHome() }
                    },
                    onSignOut = {
                        work {
                            api.logout()
                            home = null
                            screen = "login"
                        }
                    },
                )
            }
        }
    }
}

@Composable
private fun LoginScreen(
    api: PortalApi,
    busy: Boolean,
    error: String?,
    theme: String,
    onTheme: (String) -> Unit,
    onSubmit: (String, String) -> Unit,
) {
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var showPassword by remember { mutableStateOf(false) }
    var server by remember { mutableStateOf(api.server) }
    Column(
        Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 16.dp),
    ) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            ThemeSwitch(theme, onTheme)
        }
        val screenHeight = LocalConfiguration.current.screenHeightDp.dp
        BoxWithConstraints(Modifier.fillMaxWidth().padding(top = 8.dp)) {
            val vayu = maxWidth * 0.36f
            val sync = maxWidth * 0.82f
            Column {
                Image(
                    painterResource(R.drawable.vayu_logo),
                    contentDescription = "Vayu Technologies",
                    modifier = Modifier.width(vayu).heightIn(max = screenHeight * 0.18f),
                    contentScale = ContentScale.Fit,
                )
                Spacer(Modifier.height(18.dp))
                Text(
                    buildAnnotatedString {
                        append("Automate. ")
                        withStyle(SpanStyle(color = MaterialTheme.colorScheme.primary)) { append("Govern.") }
                        append(" Optimize.")
                    },
                    style = MaterialTheme.typography.headlineLarge,
                    fontWeight = FontWeight.Bold,
                    lineHeight = 38.sp,
                )
                Text(
                    "Your unified cloud operations platform.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 6.dp, bottom = 16.dp),
                )
                Image(
                    painterResource(R.drawable.cloudsync_logo),
                    contentDescription = "CloudSync",
                    modifier = Modifier.width(sync).align(Alignment.CenterHorizontally),
                    contentScale = ContentScale.FillWidth,
                )
            }
        }
        Card(
            Modifier.fillMaxWidth().padding(top = 22.dp),
            shape = RoundedCornerShape(22.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        ) {
            Column(Modifier.padding(22.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Step 1 of 2 · Credentials", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelLarge)
                Text("Welcome back", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Text("Sign in to CloudSync.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                OutlinedTextField(username, { username = it }, Modifier.fillMaxWidth(), label = { Text("Username") }, singleLine = true)
                OutlinedTextField(
                    password,
                    { password = it },
                    Modifier.fillMaxWidth(),
                    label = { Text("Password") },
                    singleLine = true,
                    visualTransformation = if (showPassword) VisualTransformation.None else PasswordVisualTransformation(),
                    trailingIcon = {
                        TextButton(onClick = { showPassword = !showPassword }) {
                            Text(if (showPassword) "Hide" else "Show")
                        }
                    },
                )
                if (!error.isNullOrBlank()) Text(error, color = Color(0xFF9B2C2C))
                Button(
                    onClick = {
                        api.server = server
                        onSubmit(username.trim(), password)
                    },
                    enabled = !busy && username.isNotBlank() && password.isNotBlank(),
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(12.dp),
                ) {
                    if (busy) CircularProgressIndicator(Modifier.size(18.dp), color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp)
                    else Text("Sign in", fontWeight = FontWeight.Bold)
                }
                OutlinedTextField(
                    server,
                    { server = it },
                    Modifier.fillMaxWidth(),
                    label = { Text("Console address") },
                    singleLine = true,
                    supportingText = { Text("On a phone, use the computer's Wi-Fi address, such as http://192.168.1.15:5080. The emulator uses http://10.0.2.2:5080.") },
                )
            }
        }
    }
}

@Composable
private fun VerifyScreen(
    busy: Boolean,
    error: String?,
    theme: String,
    onTheme: (String) -> Unit,
    onSubmit: (String) -> Unit,
    onBack: () -> Unit,
) {
    var code by remember { mutableStateOf("") }
    AuthCard(theme, onTheme) {
        Text("Step 2 of 2 · Authenticator", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text("Authenticator code", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("Enter the current 6-digit code from the app registered to this account.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        OutlinedTextField(
            code,
            { if (it.length <= 6 && it.all(Char::isDigit)) code = it },
            Modifier.fillMaxWidth(),
            label = { Text("Code") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        )
        if (!error.isNullOrBlank()) Text(error, color = Color(0xFF9B2C2C))
        Button(
            onClick = { onSubmit(code) },
            enabled = !busy && code.length == 6,
            modifier = Modifier.fillMaxWidth().height(48.dp),
            shape = RoundedCornerShape(12.dp),
        ) { Text(if (busy) "Checking…" else "Verify and enter", fontWeight = FontWeight.Bold) }
        TextButton(onClick = onBack) { Text("Use a different account") }
    }
}

@Composable
private fun EnrollScreen(
    pin: String,
    uri: String,
    busy: Boolean,
    error: String?,
    onConfirm: () -> Unit,
    onBack: () -> Unit,
) {
    AuthCard("system", {}) {
        Text("Step 2 of 2 · Authenticator", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text("Register an authenticator", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("Add this setup key in your authenticator app, then confirm this device.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(pin, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Text(uri, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (!error.isNullOrBlank()) Text(error, color = Color(0xFF9B2C2C))
        Button(
            onClick = onConfirm,
            enabled = !busy,
            modifier = Modifier.fillMaxWidth().height(48.dp),
            shape = RoundedCornerShape(12.dp),
        ) { Text(if (busy) "Saving…" else "I have added this device", fontWeight = FontWeight.Bold) }
        TextButton(onClick = onBack) { Text("Use a different account") }
    }
}

@Composable
private fun AuthCard(theme: String, onTheme: (String) -> Unit, content: @Composable () -> Unit) {
    Column(
        Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            BoxWithConstraints {
                Image(
                    painterResource(R.drawable.cloudsync_logo),
                    contentDescription = "CloudSync",
                    modifier = Modifier.width(maxWidth * 0.46f),
                    contentScale = ContentScale.FillWidth,
                )
            }
            ThemeSwitch(theme, onTheme)
        }
        Card(shape = RoundedCornerShape(22.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
            Column(Modifier.padding(22.dp), verticalArrangement = Arrangement.spacedBy(12.dp), content = { content() })
        }
    }
}

private data class MenuEntry(val id: String, val label: String, val admin: Boolean = false)

private val MenuEntries = listOf(
    MenuEntry("dashboard", "Dashboard"),
    MenuEntry("housekeeping", "Housekeeping"),
    MenuEntry("cost", "Cost"),
    MenuEntry("governance", "Governance"),
    MenuEntry("reports", "Reports"),
    MenuEntry("accounts", "AWS accounts", admin = true),
    MenuEntry("settings", "AWS connection", admin = true),
    MenuEntry("people", "People", admin = true),
    MenuEntry("audit", "Audit", admin = true),
)

@Composable
private fun ConsoleScreen(
    api: PortalApi,
    home: Home,
    busy: Boolean,
    theme: String,
    onTheme: (String) -> Unit,
    onRefresh: () -> Unit,
    onSignOut: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val admin = home.role == "admin"
    var menuOpen by remember { mutableStateOf(false) }
    val drawerWidth = 312.dp
    val drawerOffset by animateDpAsState(
        targetValue = if (menuOpen) 0.dp else -drawerWidth,
        animationSpec = tween(durationMillis = 280, easing = FastOutSlowInEasing),
        label = "menu",
    )
    val scrimAlpha by animateFloatAsState(
        targetValue = if (menuOpen) 0.38f else 0f,
        animationSpec = tween(durationMillis = 280),
        label = "scrim",
    )
    var page by remember { mutableStateOf("dashboard") }
    var opened by remember { mutableStateOf<ReportCard?>(null) }
    var document by remember { mutableStateOf<ReportDocument?>(null) }
    var reportError by remember { mutableStateOf<String?>(null) }
    var reportBusy by remember { mutableStateOf(false) }
    var pdfBusy by remember { mutableStateOf(false) }
    var pdfNote by remember { mutableStateOf<String?>(null) }

    fun openReport(card: ReportCard) {
        page = "reports"
        opened = card
        document = null
        reportError = null
        pdfNote = null
        reportBusy = true
        scope.launch {
            try {
                val account = home.accountRefs.firstOrNull()
                if (account == null || account.id == 0) {
                    reportError = "Add an AWS account from the menu before opening a report."
                    return@launch
                }
                val json = withContext(Dispatchers.IO) { api.report(card.id, account.id, account.region) }
                document = json.toReport()
            } catch (exception: ApiException) {
                reportError = exception.message
            } catch (exception: Exception) {
                reportError = exception.message ?: "The report could not be read."
            } finally {
                reportBusy = false
            }
        }
    }

    fun downloadPdf() {
        val card = opened ?: return
        val account = home.accountRefs.firstOrNull()
        if (account == null || account.id == 0) {
            pdfNote = "Add an AWS account from the menu before creating a PDF."
            return
        }
        pdfBusy = true
        pdfNote = null
        scope.launch {
            try {
                val bytes = withContext(Dispatchers.IO) { api.reportPdf(card.id, account.id, account.region) }
                val dir = File(context.cacheDir, "reports").apply { mkdirs() }
                val safe = card.code.ifBlank { card.id }.replace(Regex("[^A-Za-z0-9_-]"), "")
                val file = File(dir, "$safe.pdf")
                file.writeBytes(bytes)
                val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", file)
                val view = Intent(Intent.ACTION_VIEW)
                    .setDataAndType(uri, "application/pdf")
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                try {
                    context.startActivity(view)
                    pdfNote = "PDF ready."
                } catch (_: ActivityNotFoundException) {
                    val share = Intent(Intent.ACTION_SEND)
                        .setType("application/pdf")
                        .putExtra(Intent.EXTRA_STREAM, uri)
                        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    context.startActivity(Intent.createChooser(share, "Share report"))
                    pdfNote = "PDF ready to share."
                }
            } catch (exception: Exception) {
                pdfNote = exception.message ?: "The PDF could not be created."
            } finally {
                pdfBusy = false
            }
        }
    }

    fun choose(id: String) {
        page = id
        opened = null
        menuOpen = false
    }

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
            ConsoleHeader(onMenu = { menuOpen = true })
            Box(Modifier.weight(1f).fillMaxWidth()) {
                if (opened != null && page == "reports") {
                    ReportDetail(
                        card = opened!!,
                        document = document,
                        busy = reportBusy,
                        error = reportError,
                        pdfBusy = pdfBusy,
                        pdfNote = pdfNote,
                        onPdf = ::downloadPdf,
                        onBack = { opened = null },
                    )
                } else when (page) {
                    "housekeeping" -> TopicPage(home.housekeeping, home.scans.filter { it.kind == "housekeeping" }, home.reports.firstOrNull { it.id == "housekeeping" }, ::openReport)
                    "cost" -> TopicPage(home.cost, home.scans.filter { it.kind == "cost" || it.kind == "cost-inventory" }, home.reports.firstOrNull { it.id == "cost" }, ::openReport)
                    "governance" -> TopicPage(home.governance, home.scans.filter { it.kind == "governance" }, home.reports.firstOrNull { it.id == "governance" }, ::openReport)
                    "reports" -> ReportsPage(home.reports, ::openReport)
                    "accounts" -> ScopeScreen(api, onRefresh)
                    "settings" -> SettingsScreen(api, onRefresh)
                    "people" -> PeopleScreen(api)
                    "audit" -> AuditScreen(api)
                    else -> DashboardPage(home)
                }
            }
        }
        if (menuOpen || drawerOffset > -drawerWidth + 8.dp) {
            Box(
                Modifier
                    .fillMaxSize()
                    .zIndex(1f)
                    .background(Color.Black.copy(alpha = scrimAlpha))
                    .clickable { menuOpen = false },
            )
            Column(
                Modifier
                    .zIndex(2f)
                    .fillMaxHeight()
                    .width(drawerWidth)
                    .offset(x = drawerOffset)
                    .background(MaterialTheme.colorScheme.surface),
            ) {
                AppDrawer(home, admin, page, theme, onTheme, { menuOpen = false; onSignOut() }, ::choose)
            }
        }
    }
}

@Composable
private fun AppDrawer(
    home: Home,
    admin: Boolean,
    page: String,
    theme: String,
    onTheme: (String) -> Unit,
    onSignOut: () -> Unit,
    onChoose: (String) -> Unit,
) {
    Column(
        Modifier
            .fillMaxSize()
            .statusBarsPadding()
            .navigationBarsPadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 12.dp, vertical = 12.dp),
    ) {
        Image(
            painterResource(R.drawable.cloudsync_logo),
            "CloudSync",
            Modifier.fillMaxWidth(0.62f).padding(start = 8.dp, bottom = 4.dp),
            contentScale = ContentScale.FillWidth,
        )
        Image(
            painterResource(R.drawable.vayu_logo),
            "Vayu Technologies",
            Modifier.fillMaxWidth(0.22f).padding(start = 8.dp, bottom = 8.dp),
            contentScale = ContentScale.Fit,
        )
        Text(home.username, modifier = Modifier.padding(start = 16.dp), fontWeight = FontWeight.Bold)
        Text(home.role.replaceFirstChar { it.uppercase() }, modifier = Modifier.padding(start = 16.dp, bottom = 8.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        Text("WORK", modifier = Modifier.padding(start = 16.dp, top = 8.dp, bottom = 4.dp), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
        MenuEntries.filter { !it.admin }.forEach { entry ->
            NavigationDrawerItem(
                label = { Text(entry.label) },
                selected = page == entry.id,
                onClick = { onChoose(entry.id) },
                icon = { Icon(menuIcon(entry.id), contentDescription = entry.label) },
                shape = RoundedCornerShape(12.dp),
            )
        }
        if (admin) {
            Text("ADMINISTRATION", modifier = Modifier.padding(start = 16.dp, top = 12.dp, bottom = 4.dp), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
            MenuEntries.filter { it.admin }.forEach { entry ->
                NavigationDrawerItem(
                    label = { Text(entry.label) },
                    selected = page == entry.id,
                    onClick = { onChoose(entry.id) },
                    icon = { Icon(menuIcon(entry.id), contentDescription = entry.label) },
                    shape = RoundedCornerShape(12.dp),
                )
            }
        }
        Spacer(Modifier.height(12.dp))
        ThemeSwitch(theme, onTheme)
        TextButton(onClick = onSignOut, modifier = Modifier.padding(top = 8.dp)) { Text("Sign out") }
    }
}

@Composable
private fun ConsoleHeader(onMenu: () -> Unit) {
    BoxWithConstraints(
        Modifier
            .fillMaxWidth()
            .statusBarsPadding()
            .padding(start = 4.dp, end = 16.dp, top = 4.dp, bottom = 4.dp),
    ) {
        val sync = (maxWidth * 0.46f).coerceIn(128.dp, 210.dp)
        val vayu = (maxWidth * 0.18f).coerceIn(56.dp, 92.dp)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.size(48.dp).systemGestureExclusion().clickable(onClick = onMenu),
                contentAlignment = Alignment.Center,
            ) {
                Icon(Icons.Filled.Menu, contentDescription = "Open menu")
            }
            Image(painterResource(R.drawable.cloudsync_logo), "CloudSync", Modifier.width(sync), contentScale = ContentScale.FillWidth)
            Spacer(Modifier.weight(1f))
            Image(painterResource(R.drawable.vayu_logo), "Vayu Technologies", Modifier.width(vayu), contentScale = ContentScale.Fit)
        }
    }
}

@Composable
private fun DashboardPage(home: Home) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("CONSOLE", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
        Text("Dashboard", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text("Stored reads for ${home.org}. Charts use only counts saved with a scan.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text("${home.username} · ${home.role.replaceFirstChar { it.uppercase() }}", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        val countLabel = if (home.mode == "msp") "Customers" else "Products"
        val countValue = if (home.mode == "msp") home.customers else home.products
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Metric("Accounts", home.accounts.toString(), Modifier.weight(1f))
            Metric(countLabel, countValue.toString(), Modifier.weight(1f))
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Metric("AWS connection", home.aws, Modifier.weight(1f))
            Metric("High findings", home.highOpen.toString(), Modifier.weight(1f))
        }
        ChartCard("Housekeeping severity", home.housekeeping)
        ChartCard("Governance severity", home.governance)
        ChartCard("Cost breakdown", home.cost)
        if (home.accountLines.isNotEmpty()) {
            SurfaceCard("Accounts") {
                home.accountLines.forEach { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
        }
        SurfaceCard("Recent scans") { ScanTable(home.scans) }
        SurfaceCard("Activity log") {
            if (home.logs.isEmpty()) Text("Sign-in and scan activity will be listed here.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            home.logs.forEach { log ->
                Text("${log.whenText} · ${log.person}", style = MaterialTheme.typography.labelMedium)
                Text("${log.action}  ${log.detail}", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
                Spacer(Modifier.height(8.dp))
            }
        }
    }
}

@Composable
private fun TopicPage(topic: Topic, scans: List<ScanRow>, group: ReportGroup?, onOpen: (ReportCard) -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(group?.label ?: "Topic", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
        Text(group?.headline ?: "", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text(group?.blurb ?: "", color = MaterialTheme.colorScheme.onSurfaceVariant)
        ChartCard("Stored breakdown", topic)
        SurfaceCard("Recent reads") { ScanTable(scans) }
        group?.reports?.forEach { report ->
            Card(
                Modifier.clickable { onOpen(report) },
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            ) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(report.code, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelLarge)
                    Text(report.title, fontWeight = FontWeight.Bold)
                    Text(report.audience.uppercase(), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall)
                    Text(report.summary, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("Open chart and table", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelMedium)
                }
            }
        }
    }
}

@Composable
private fun ReportsPage(groups: List<ReportGroup>, onOpen: (ReportCard) -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Text("Reports", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text("Open a report to read the selected account. Each category has its own chart and table.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        groups.forEach { group ->
            Text(group.label, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text(group.blurb, color = MaterialTheme.colorScheme.onSurfaceVariant)
            group.reports.forEach { report ->
                Card(
                    Modifier.clickable { onOpen(report) },
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                ) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("${report.code} · ${report.audience}", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelMedium)
                        Text(report.title, fontWeight = FontWeight.Bold)
                        Text(report.summary, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

@Composable
private fun ReportDetail(
    card: ReportCard,
    document: ReportDocument?,
    busy: Boolean,
    error: String?,
    pdfBusy: Boolean,
    pdfNote: String?,
    onPdf: () -> Unit,
    onBack: () -> Unit,
) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("Back") }
            Spacer(Modifier.weight(1f))
            Button(
                onClick = onPdf,
                enabled = !busy && !pdfBusy,
                shape = RoundedCornerShape(12.dp),
            ) { Text(if (pdfBusy) "Preparing PDF…" else "Download PDF") }
        }
        if (!pdfNote.isNullOrBlank()) Text(pdfNote, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(card.code, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
        Text(document?.title ?: card.title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text(document?.subtitle ?: card.summary, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (busy) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.primary)
                Text("Reading the account…")
            }
        }
        if (!error.isNullOrBlank()) Text(error, color = Color(0xFF9B2C2C))
        document?.let { report ->
            if (report.summary.isNotBlank()) Text(report.summary)
            if (report.kpis.isNotEmpty()) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    report.kpis.take(2).forEach { (label, value) -> Metric(label, value, Modifier.weight(1f)) }
                }
                if (report.kpis.size > 2) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        report.kpis.drop(2).take(2).forEach { (label, value) -> Metric(label, value, Modifier.weight(1f)) }
                    }
                }
            }
            BarCard(report.chartTitle.ifBlank { "Breakdown" }, report.chart, report.money)
            report.sections.forEach { section ->
                Text(section.title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                BarCard(section.chartTitle.ifBlank { "In this category" }, section.chart, section.money)
                SurfaceCard("Table") {
                    Text("Swipe sideways to read every column.", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
                    DataTable(section.columns, section.rows)
                }
            }
            if (report.notes.isNotEmpty()) {
                SurfaceCard("How to read this report") {
                    report.notes.forEach { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                }
            }
        }
    }
}

@Composable
private fun BarCard(title: String, bars: List<Bar>, money: Boolean) {
    val visible = bars.filter { it.value > 0 }
    SurfaceCard(title) {
        if (visible.isEmpty()) {
            Text("No figures in this category.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            val peak = visible.maxOf { it.value }.coerceAtLeast(0.01)
            visible.forEachIndexed { index, bar ->
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp)) {
                    Text(bar.label, Modifier.widthIn(min = 72.dp, max = 120.dp), style = MaterialTheme.typography.bodySmall)
                    Box(
                        Modifier
                            .weight(1f)
                            .height(12.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(MaterialTheme.colorScheme.outline.copy(alpha = 0.35f)),
                    ) {
                        Box(
                            Modifier
                                .fillMaxHeight()
                                .fillMaxWidth((bar.value / peak).toFloat().coerceIn(0.04f, 1f))
                                .background(barTone(bar.label, index)),
                        )
                    }
                    Text(formatBar(bar.value, money), Modifier.padding(start = 8.dp), fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
private fun DataTable(columns: List<String>, rows: List<List<String>>) {
    if (columns.isEmpty() || rows.isEmpty()) {
        Text("No rows in this category.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        return
    }
    Column(Modifier.horizontalScroll(rememberScrollState())) {
        Row(
            Modifier.background(Color(0xFF0C2344)).padding(vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            columns.forEach { label ->
                Text(label, Modifier.width(columnWidth(label)).padding(horizontal = 8.dp), color = Color.White, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.labelMedium)
            }
        }
        rows.forEachIndexed { index, row ->
            Row(
                Modifier
                    .background(if (index % 2 == 0) Color.Transparent else MaterialTheme.colorScheme.primary.copy(alpha = 0.08f))
                    .padding(vertical = 8.dp),
                verticalAlignment = Alignment.Top,
            ) {
                columns.forEachIndexed { column, label ->
                    Text(
                        row.getOrElse(column) { "-" },
                        Modifier.width(columnWidth(label)).padding(horizontal = 8.dp),
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.4f))
        }
    }
}

@Composable
private fun ChartCard(title: String, topic: Topic) {
    SurfaceCard(title) {
        Text(
            topic.caption.ifBlank { "No scan with a saved breakdown yet." },
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            style = MaterialTheme.typography.bodySmall,
        )
        if (topic.series.isEmpty()) {
            Text("This chart stays empty until a scan stores counts.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            val peak = topic.series.maxOf { it.value }.coerceAtLeast(1)
            topic.series.forEach { point ->
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp)) {
                    Text(point.label, Modifier.widthIn(min = 72.dp, max = 110.dp), style = MaterialTheme.typography.bodySmall)
                    Box(
                        Modifier
                            .weight(1f)
                            .height(12.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(MaterialTheme.colorScheme.outline.copy(alpha = 0.35f)),
                    ) {
                        Box(
                            Modifier
                                .fillMaxHeight()
                                .fillMaxWidth(point.value / peak.toFloat())
                                .background(point.tone),
                        )
                    }
                    Text(point.value.toString(), Modifier.padding(start = 8.dp), fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
private fun SurfaceCard(title: String, content: @Composable () -> Unit) {
    Card(shape = RoundedCornerShape(16.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            content()
        }
    }
}

@Composable
private fun Metric(label: String, value: String, modifier: Modifier) {
    Card(
        modifier,
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Box(Modifier.fillMaxWidth().height(3.dp).background(MaterialTheme.colorScheme.primary))
        Column(Modifier.padding(14.dp)) {
            Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
            Text(value, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 4.dp))
        }
    }
}

@Composable
private fun ScanTable(scans: List<ScanRow>) {
    if (scans.isEmpty()) {
        Text("Scans you run will be listed here.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        return
    }
    scans.forEach { scan ->
        Column(Modifier.padding(vertical = 6.dp)) {
            Text("${scan.kind} · ${scan.account}", fontWeight = FontWeight.SemiBold)
            Text("${scan.whenText} · ${scan.region} · ${scan.total} items · high ${scan.high} · ${scan.actor}", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.outline)
    }
}

@Composable
private fun ThemeSwitch(selected: String, onSelect: (String) -> Unit) {
    Row(
        Modifier
            .clip(RoundedCornerShape(999.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(999.dp))
            .padding(3.dp),
    ) {
        listOf("light" to "Light", "dark" to "Dark", "system" to "System").forEach { (id, label) ->
            val on = selected == id
            Text(
                label,
                modifier = Modifier
                    .clip(RoundedCornerShape(999.dp))
                    .background(if (on) MaterialTheme.colorScheme.primary else Color.Transparent)
                    .clickable { onSelect(id) }
                    .padding(horizontal = 8.dp, vertical = 6.dp),
                color = if (on) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.labelMedium,
                maxLines = 1,
            )
        }
    }
}

private fun JSONObject.toHome(): Home {
    fun topic(name: String): Topic {
        val node = optJSONObject(name) ?: JSONObject()
        val series = node.optJSONArray("series")
        val points = mutableListOf<Point>()
        if (series != null) {
            for (index in 0 until series.length()) {
                val item = series.getJSONObject(index)
                points.add(Point(item.optString("label"), item.optInt("value"), item.optString("tone", "#1B4F8A").toColor()))
            }
        }
        return Topic(node.optString("caption"), points)
    }
    fun scans(): List<ScanRow> {
        val array = optJSONArray("scans") ?: return emptyList()
        return List(array.length()) { index ->
            val item = array.getJSONObject(index)
            ScanRow(item.optString("when"), item.optString("kind"), item.optString("account_name"), item.optString("region"), item.optInt("total"), item.optInt("high"), item.optString("actor"))
        }
    }
    fun logs(): List<LogRow> {
        val array = optJSONArray("logs") ?: return emptyList()
        return List(array.length()) { index ->
            val item = array.getJSONObject(index)
            LogRow(item.optString("when"), item.optString("username"), item.optString("action"), item.optString("detail"))
        }
    }
    fun reports(): List<ReportGroup> {
        val array = optJSONArray("reports") ?: return emptyList()
        return List(array.length()) { index ->
            val group = array.getJSONObject(index)
            val cards = group.optJSONArray("reports")
            val items = if (cards == null) emptyList() else List(cards.length()) { cardIndex ->
                val card = cards.getJSONObject(cardIndex)
                ReportCard(card.optString("id"), card.optString("code"), card.optString("title"), card.optString("audience"), card.optString("summary"))
            }
            ReportGroup(group.optString("id"), group.optString("label"), group.optString("headline"), group.optString("blurb"), items)
        }
    }
    val user = optJSONObject("user") ?: JSONObject()
    val accounts = optJSONArray("accounts")
    val lines = if (accounts == null) emptyList() else List(accounts.length()) { index ->
        val item = accounts.getJSONObject(index)
        "${item.optString("name")} · ${item.optString("account_id")} · ${item.optString("region")}"
    }
    val accountRefs = if (accounts == null) emptyList() else List(accounts.length()) { index ->
        val item = accounts.getJSONObject(index)
        AccountRef(item.optInt("id"), item.optString("name"), item.optString("account_id"), item.optString("region"))
    }
    return Home(
        username = user.optString("username"),
        role = user.optString("role"),
        org = optString("org_name"),
        accounts = optInt("account_count"),
        products = optInt("product_count"),
        customers = optInt("customer_count"),
        mode = optString("mode"),
        aws = optString("aws"),
        highOpen = optInt("high_open"),
        housekeeping = topic("housekeeping"),
        governance = topic("governance"),
        cost = topic("cost"),
        scans = scans(),
        logs = logs(),
        accountLines = lines,
        accountRefs = accountRefs,
        reports = reports(),
    )
}

private fun JSONObject.toReport(): ReportDocument {
    fun bars(node: JSONObject): List<Bar> {
        val array = node.optJSONArray("chart") ?: return emptyList()
        return List(array.length()) { index ->
            val item = array.getJSONObject(index)
            Bar(item.optString("label"), item.optDouble("value"))
        }
    }
    val kpiArray = optJSONArray("kpis")
    val kpis = if (kpiArray == null) emptyList() else List(kpiArray.length()) { index ->
        val item = kpiArray.getJSONObject(index)
        item.optString("label") to item.optString("value")
    }
    val noteArray = optJSONArray("notes")
    val notes = if (noteArray == null) emptyList() else List(noteArray.length()) { noteArray.optString(it) }
    val sectionArray = optJSONArray("sections")
    val sections = if (sectionArray == null) emptyList() else List(sectionArray.length()) { index ->
        val section = sectionArray.getJSONObject(index)
        val columnsArray = section.optJSONArray("columns")
        val columns = if (columnsArray == null) emptyList() else List(columnsArray.length()) { columnsArray.optString(it) }
        val rowArray = section.optJSONArray("rows")
        val rows = if (rowArray == null) emptyList() else List(rowArray.length()) { rowIndex ->
            val row = rowArray.optJSONArray(rowIndex)
            if (row == null) emptyList() else List(row.length()) { row.optString(it) }
        }
        ReportSection(
            section.optString("title"),
            section.optString("chart_title"),
            section.optBoolean("money"),
            bars(section),
            columns,
            rows,
        )
    }
    return ReportDocument(
        code = optString("code"),
        domain = optString("domain"),
        title = optString("title"),
        audience = optString("audience"),
        summary = optString("summary"),
        subtitle = optString("subtitle"),
        money = optBoolean("money"),
        kpis = kpis,
        chartTitle = optString("chart_title"),
        chart = bars(this),
        notes = notes,
        sections = sections,
    )
}

private fun columnWidth(label: String) = when (label) {
    "Severity", "Priority", "Status" -> 96.dp
    "Category", "Service", "Pillars" -> 120.dp
    "Resource", "Saving / month" -> 140.dp
    "Finding", "Action", "Recommendation" -> 220.dp
    else -> 150.dp
}

private fun barTone(label: String, index: Int): Color {
    return when (label.uppercase().substringBefore(" ")) {
        "HIGH", "SECURITY" -> Color(0xFF9B2C2C)
        "MEDIUM" -> Color(0xFF9A6B12)
        "LOW", "RELIABILITY" -> Color(0xFF1B4F8A)
        "INFO" -> Color(0xFF8AA0BD)
        else -> listOf(Color(0xFFFF9900), Color(0xFF1B4F8A), Color(0xFF0C2344), Color(0xFF3D74B8))[index % 4]
    }
}

private fun formatBar(value: Double, money: Boolean): String {
    if (money) {
        return if (kotlin.math.abs(value) >= 100) "$${value.toLong()}" else "$" + String.format("%.2f", value)
    }
    return if (value == value.toLong().toDouble()) value.toLong().toString() else String.format("%.1f", value)
}

private fun String.toColor(): Color {
    val hex = trim().removePrefix("#")
    val value = hex.toLongOrNull(16) ?: return Color(0xFF1B4F8A)
    return if (hex.length == 6) Color(0xFF000000 or value) else Color(value)
}
