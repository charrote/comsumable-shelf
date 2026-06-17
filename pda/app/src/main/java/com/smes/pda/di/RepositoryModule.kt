package com.smes.pda.di

import com.smes.pda.data.repository.*
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object RepositoryModule {

    @Provides
    @Singleton
    fun provideAuthRepository(authRepository: AuthRepository): AuthRepository = authRepository

    @Provides
    @Singleton
    fun provideReceiptRepository(receiptRepository: ReceiptRepository): ReceiptRepository = receiptRepository

    @Provides
    @Singleton
    fun provideIssueRepository(issueRepository: IssueRepository): IssueRepository = issueRepository

    @Provides
    @Singleton
    fun provideInventoryRepository(inventoryRepository: InventoryRepository): InventoryRepository = inventoryRepository
}
