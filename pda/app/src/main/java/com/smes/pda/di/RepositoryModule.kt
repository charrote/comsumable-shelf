package com.smes.pda.di

import com.smes.pda.data.repository.*
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

// Repositories are auto-provided via @Inject constructor() on each class.
// This module is kept for future bindings to interfaces if needed.
@Module
@InstallIn(SingletonComponent::class)
abstract class RepositoryModule {
    // Bindings go here when repositories implement interfaces
}
