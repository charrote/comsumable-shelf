package com.smes.pda

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class ConsumableShelfApp : Application() {
    override fun onCreate() {
        super.onCreate()
    }
}
