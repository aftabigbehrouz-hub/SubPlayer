// JNI bridge between SubPlayer (Kotlin) and whisper.cpp.
// One native "session" holds the model; transcribe() runs on a background thread,
// progress and cancellation are exchanged through atomics (polled from Kotlin).
#include <jni.h>
#include <android/log.h>
#include <atomic>
#include <string>
#include <vector>
#include "whisper.h"

#define TAG "SubPlayerWhisper"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

struct Session {
    whisper_context *ctx = nullptr;
    std::atomic<int> progress{0};
    std::atomic<bool> cancel{false};
    std::string vadPath;
};

static void on_progress(whisper_context *, whisper_state *, int p, void *ud) {
    static_cast<Session *>(ud)->progress.store(p);
}

static bool on_abort(void *ud) {
    return static_cast<Session *>(ud)->cancel.load();
}

static bool on_encoder_begin(whisper_context *, whisper_state *, void *ud) {
    return !static_cast<Session *>(ud)->cancel.load();   // false = stop
}

extern "C" JNIEXPORT jlong JNICALL
Java_com_behrouz_subplayer_asr_WhisperNative_open(JNIEnv *env, jobject, jstring modelPath, jstring vadPath) {
    const char *mp = env->GetStringUTFChars(modelPath, nullptr);
    whisper_context_params cp = whisper_context_default_params();
    cp.use_gpu = false;
    whisper_context *ctx = whisper_init_from_file_with_params(mp, cp);
    env->ReleaseStringUTFChars(modelPath, mp);
    if (!ctx) return 0;
    auto *s = new Session();
    s->ctx = ctx;
    if (vadPath != nullptr) {
        const char *vp = env->GetStringUTFChars(vadPath, nullptr);
        s->vadPath = vp;
        env->ReleaseStringUTFChars(vadPath, vp);
    }
    return reinterpret_cast<jlong>(s);
}

extern "C" JNIEXPORT void JNICALL
Java_com_behrouz_subplayer_asr_WhisperNative_close(JNIEnv *, jobject, jlong h) {
    auto *s = reinterpret_cast<Session *>(h);
    if (!s) return;
    whisper_free(s->ctx);
    delete s;
}

extern "C" JNIEXPORT jint JNICALL
Java_com_behrouz_subplayer_asr_WhisperNative_progress(JNIEnv *, jobject, jlong h) {
    return reinterpret_cast<Session *>(h)->progress.load();
}

extern "C" JNIEXPORT void JNICALL
Java_com_behrouz_subplayer_asr_WhisperNative_cancel(JNIEnv *, jobject, jlong h) {
    reinterpret_cast<Session *>(h)->cancel.store(true);
}

// Returns one string per segment: "<startMs>\t<endMs>\t<text>"; null if cancelled/failed.
extern "C" JNIEXPORT jobjectArray JNICALL
Java_com_behrouz_subplayer_asr_WhisperNative_transcribe(JNIEnv *env, jobject, jlong h,
                                                        jfloatArray pcm, jstring lang,
                                                        jint threads, jstring prompt) {
    auto *s = reinterpret_cast<Session *>(h);
    s->progress.store(0);

    const char *lg = env->GetStringUTFChars(lang, nullptr);
    std::string language(lg);
    env->ReleaseStringUTFChars(lang, lg);

    std::string initialPrompt;
    if (prompt != nullptr) {
        const char *pp = env->GetStringUTFChars(prompt, nullptr);
        initialPrompt = pp;
        env->ReleaseStringUTFChars(prompt, pp);
    }

    whisper_full_params p = whisper_full_default_params(WHISPER_SAMPLING_GREEDY);
    p.n_threads = threads;
    p.language = language.c_str();
    p.translate = false;
    p.print_progress = false;
    p.print_realtime = false;
    p.print_timestamps = false;
    p.print_special = false;
    p.suppress_nst = true;               // drop "(Musik)" style non-speech tokens
    p.token_timestamps = true;           // accurate timing when splitting lines
    p.max_len = 84;                      // subtitle-sized lines (2 rows of ~42)
    p.split_on_word = true;
    p.progress_callback = on_progress;
    p.progress_callback_user_data = s;
    p.abort_callback = on_abort;
    p.abort_callback_user_data = s;
    p.encoder_begin_callback = on_encoder_begin;
    p.encoder_begin_callback_user_data = s;
    if (!initialPrompt.empty()) p.initial_prompt = initialPrompt.c_str();
    if (!s->vadPath.empty()) {
        p.vad = true;                    // skip silence: faster, no hallucinated text
        p.vad_model_path = s->vadPath.c_str();
        p.vad_params = whisper_vad_default_params();
    }

    jsize n = env->GetArrayLength(pcm);
    std::vector<float> audio(n);
    env->GetFloatArrayRegion(pcm, 0, n, audio.data());

    int rc = whisper_full(s->ctx, p, audio.data(), (int) audio.size());
    if (rc != 0 || s->cancel.load()) {
        LOGI("whisper_full rc=%d cancel=%d", rc, (int) s->cancel.load());
        return nullptr;
    }

    int ns = whisper_full_n_segments(s->ctx);
    jclass strCls = env->FindClass("java/lang/String");
    jobjectArray out = env->NewObjectArray(ns, strCls, nullptr);
    for (int i = 0; i < ns; i++) {
        long long t0 = whisper_full_get_segment_t0(s->ctx, i) * 10;   // centiseconds -> ms
        long long t1 = whisper_full_get_segment_t1(s->ctx, i) * 10;
        const char *txt = whisper_full_get_segment_text(s->ctx, i);
        std::string line = std::to_string(t0) + "\t" + std::to_string(t1) + "\t" + (txt ? txt : "");
        // Build a jstring from UTF-8 bytes safely (NewStringUTF needs modified UTF-8).
        jbyteArray bytes = env->NewByteArray((jsize) line.size());
        env->SetByteArrayRegion(bytes, 0, (jsize) line.size(), reinterpret_cast<const jbyte *>(line.data()));
        jclass sCls = env->FindClass("java/lang/String");
        jmethodID ctor = env->GetMethodID(sCls, "<init>", "([BLjava/lang/String;)V");
        jstring enc = env->NewStringUTF("UTF-8");
        auto js = (jstring) env->NewObject(sCls, ctor, bytes, enc);
        env->SetObjectArrayElement(out, i, js);
        env->DeleteLocalRef(js);
        env->DeleteLocalRef(enc);
        env->DeleteLocalRef(bytes);
        env->DeleteLocalRef(sCls);
    }
    return out;
}
