package com.henriquesebastiao.downtify.core.data.di

import javax.inject.Qualifier

/** A scope that lives as long as the process: for work that must outlive a screen. */
@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class ApplicationScope
