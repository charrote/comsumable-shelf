package com.smes.pda.di

import android.content.Context
import com.smes.pda.data.api.ApiConfig
import com.smes.pda.data.api.ApiService
import com.smes.pda.data.api.AuthInterceptor
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
    fun provideAuthInterceptor(@ApplicationContext context: Context): AuthInterceptor {
        return AuthInterceptor(context)
    }

    @Provides
    @Singleton
    fun provideApiService(authInterceptor: AuthInterceptor): ApiService {
        return ApiService(authInterceptor)
    }

    @Provides
    @Singleton
    fun provideApiConfig(): ApiConfig = ApiConfig.instance
}
