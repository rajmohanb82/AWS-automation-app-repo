package com.vayutechnologies.cloudsync

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.vayutechnologies.cloudsync.data.PortalApi
import com.vayutechnologies.cloudsync.ui.CloudSyncApp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val api = PortalApi(applicationContext)
        setContent {
            CloudSyncApp(api)
        }
    }
}
