package com.smes.pda.di

import com.smes.pda.data.repository.*
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class RepositoryModule {
    // Repositories are auto-provided via @Inject constructor on each class.
    // Bindings go here when repositories implement interfaces.
}
