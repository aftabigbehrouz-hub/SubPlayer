pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        // only Myket's billing library is taken from JitPack
        maven("https://jitpack.io") { content { includeGroup("com.github.myketstore") } }
    }
}

rootProject.name = "SubPlayer"
include(":app")
