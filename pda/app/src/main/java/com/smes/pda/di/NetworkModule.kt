package com.smes.pda.di

import android.content.Context
import com.smes.pda.data.api.ApiConfig
import com.smes.pda.data.api.HttpService
import com.smes.pda.data.local.SettingsDataStore
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideSettingsDataStore(@ApplicationContext context: Context): SettingsDataStore {
        return SettingsDataStore(context)
    }

    @Provides
    @Singleton
    fun provideHttpService(settingsDataStore: SettingsDataStore): HttpService {
        return HttpService(settingsDataStore)
    }

    @Provides
    @Singleton
    fun provideApiConfig(): ApiConfig = ApiConfig.instance
}
