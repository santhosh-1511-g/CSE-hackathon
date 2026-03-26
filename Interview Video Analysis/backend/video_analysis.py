import cv2
import os
import tempfile
from typing import Dict, Any, List, Tuple

import numpy as np
from deepface import DeepFace
import speech_recognition as sr
import imageio_ffmpeg

# ✅ Ensure MoviePy/ImageIO can find FFmpeg (especially for Python 3.13)
os.environ["IMAGEIO_FFMPEG_EXE"] = imageio_ffmpeg.get_ffmpeg_exe()

try:
    from moviepy import VideoFileClip  # MoviePy 2.x
except ImportError:
    from moviepy.editor import VideoFileClip  # MoviePy 1.x

def analyze_video(video_file) -> Dict[str, Any]:
    temp_path = None
    try:
        # Save uploaded video temporarily
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        temp_path = temp_file.name
        video_file.save(temp_path)
        temp_file.close()

        metrics = analyze_video_path(temp_path)
        transcript = extract_audio_text(temp_path)

        # Add transcript into metrics
        metrics["transcript"] = transcript

        cleanup(temp_path)
        return metrics

    except Exception as e:
        import traceback
        traceback.print_exc()
        cleanup(temp_path)
        return {"error": f"Video analysis failed: {str(e)}"}


def analyze_video_path(video_path: str) -> Dict[str, Any]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"error": "Unable to open video"}

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    sample_every = max(int(fps), 1)  # sample ~1 frame/sec

    # OpenCV Haar cascades for basic face/eye detection
    haar_dir = cv2.data.haarcascades
    face_cascade = cv2.CascadeClassifier(os.path.join(haar_dir, 'haarcascade_frontalface_default.xml'))
    eye_cascade = cv2.CascadeClassifier(os.path.join(haar_dir, 'haarcascade_eye.xml'))

    first_face_embedding = None
    identity_mismatch_frames = 0
    multi_face_frames = 0
    no_face_frames = 0
    gaze_away_frames = 0
    head_pose_out_frames = 0
    motion_scores: List[float] = []

    dominant_emotion = None
    emotion_probs = None
    prev_gray = None

    frame_index = 0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    # Heuristic thresholds
    center_gaze_thresh = max(width, height) * 0.12
    center_head_thresh = max(width, height) * 0.25

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_index % sample_every != 0:
            frame_index += 1
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect faces
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        face_count = len(faces)
        if face_count == 0:
            no_face_frames += 1
        if face_count > 1:
            multi_face_frames += 1

        # Use first face for identity and heuristics
        if face_count >= 1:
            (x, y, w, h) = faces[0]
            face_crop = frame[y:y+h, x:x+w]

            # Identity consistency using DeepFace embedding on cropped face
            try:
                if face_crop.size != 0:
                    emb = DeepFace.represent(face_crop, model_name='Facenet512', enforce_detection=False)
                    if emb and len(emb) > 0:
                        vec = np.array(emb[0]['embedding'], dtype=np.float32)
                        if first_face_embedding is None:
                            first_face_embedding = vec
                        else:
                            sim = cosine_similarity(first_face_embedding, vec)
                            if sim < 0.45:
                                identity_mismatch_frames += 1
            except Exception:
                pass

            # Gaze heuristic: face center offset from frame center
            face_center = np.array([x + w/2.0, y + h/2.0])
            img_center = np.array([width/2.0, height/2.0])
            if np.linalg.norm(face_center - img_center) > center_gaze_thresh:
                gaze_away_frames += 1

            # Head pose proxy: extreme vertical offset or too small face size
            face_size_ratio = max(w, h) / max(1, max(width, height))
            if abs((y + h/2.0) - img_center[1]) > center_head_thresh or face_size_ratio < 0.08:
                head_pose_out_frames += 1

        # Motion/activity via grayscale diff
        try:
            if prev_gray is not None:
                diff = cv2.absdiff(gray, prev_gray)
                motion = float(np.mean(diff)) / 255.0
                motion_scores.append(motion)
            prev_gray = gray
        except Exception:
            pass

        # Grab emotion once (first usable frame)
        if dominant_emotion is None:
            try:
                face_result = DeepFace.analyze(rgb, actions=['emotion'], enforce_detection=False)
                if isinstance(face_result, list) and face_result:
                    dominant_emotion = face_result[0].get('dominant_emotion')
                    emotion_probs = face_result[0].get('emotion')
                elif isinstance(face_result, dict):
                    dominant_emotion = face_result.get('dominant_emotion')
                    emotion_probs = face_result.get('emotion')
            except Exception:
                dominant_emotion = None

        frame_index += 1

    cap.release()

    total_sampled = max(1, frame_index // sample_every)
    motion_intensity_avg = float(np.mean(motion_scores)) if motion_scores else 0.0

    # Audio features
    vad_ratio, speech_segments = vad_speech_features(video_path)

    # Build metrics
    metrics: Dict[str, Any] = {
        "emotion": dominant_emotion or "unknown",
        "video": {
            "sampledFrames": total_sampled,
            "multiFaceFrames": multi_face_frames,
            "noFaceFrames": no_face_frames,
            "identityMismatchFrames": identity_mismatch_frames,
            "gazeAwayFrames": gaze_away_frames,
            "headPoseOutFrames": head_pose_out_frames,
            "motionIntensityAvg": round(motion_intensity_avg, 3),
        },
        "audio": {
            "speechRatio": round(vad_ratio, 3),
            "speechSegments": int(speech_segments),
        },
        "emotionProbabilities": {k: round(v, 2) for k, v in emotion_probs.items()} if emotion_probs else {},
    }

    # Simple heuristic classifier with reasons
    reasons: List[str] = []
    v = metrics["video"]
    a = metrics["audio"]
    def ratio(n):
        return n / max(1, v["sampledFrames"])

    if ratio(v["identityMismatchFrames"]) > 0.05:
        reasons.append("Identity mismatch")
    if ratio(v["multiFaceFrames"]) > 0.02:
        reasons.append("Multiple faces detected")
    if ratio(v["noFaceFrames"]) > 0.1:
        reasons.append("Face not visible often")
    if ratio(v["gazeAwayFrames"]) > 0.25:
        reasons.append("Frequent gaze off-screen")
    if ratio(v["headPoseOutFrames"]) > 0.2:
        reasons.append("Head pose abnormal")
    if a["speechRatio"] > 0.35:
        reasons.append("Too much speech")

    verdict = "Suspicious" if len(reasons) > 0 else "Clean"
    metrics["classification"] = {"verdict": verdict, "reasons": reasons}

    return metrics


def extract_audio_text(video_path):
    recognizer = sr.Recognizer()
    text = ""
    tmp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    audio_path = tmp_audio.name
    tmp_audio.close()

    try:
        # 🎧 Convert video to WAV using MoviePy
        clip = VideoFileClip(video_path)
        clip.audio.write_audiofile(audio_path, codec='pcm_s16le', logger=None)
        clip.close()  # ✅ Release MoviePy resources

        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
    except Exception as e:
        text = f"[Audio error: {str(e)}]"
    finally:
        cleanup(audio_path)

    return text


def cleanup(path):
    """Safely remove temporary files if they exist."""
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except PermissionError:
            # 🕒 Wait briefly and try again
            import time
            time.sleep(0.5)
            try:
                os.remove(path)
            except Exception:
                pass


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a is None or b is None:
        return 0.0
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def vad_speech_features(video_path: str) -> Tuple[float, int]:
    """Simple energy-based VAD: compute RMS per 30ms frame and threshold.
    Returns (speech_ratio, speech_segments).
    """
    tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    audio_path = tmp_wav.name
    tmp_wav.close()

    try:
        clip = VideoFileClip(video_path)
        clip.audio.write_audiofile(audio_path, fps=16000, nbytes=2, codec='pcm_s16le', ffmpeg_params=["-ac", "1"], logger=None)
        clip.close()

        import wave
        import struct
        wf = wave.open(audio_path, 'rb')
        sample_rate = wf.getframerate()
        num_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        if sample_rate != 16000 or num_channels != 1 or sampwidth != 2:
            wf.close()
            return 0.0, 0

        frame_ms = 30
        frame_samples = int(sample_rate * frame_ms / 1000)
        speech_frames = 0
        total_frames = 0
        speech_segments = 0
        in_speech = False

        while True:
            frames = wf.readframes(frame_samples)
            if len(frames) < frame_samples * 2:
                break
            total_frames += 1
            # unpack 16-bit PCM
            data = struct.unpack('<' + 'h' * frame_samples, frames)
            arr = np.array(data, dtype=np.float32)
            rms = float(np.sqrt(np.mean(np.square(arr))))
            # dynamic threshold based on running median approximation
            # use fixed heuristic threshold suitable for typical mic levels
            is_speech = rms > 500.0
            if is_speech:
                speech_frames += 1
            if is_speech and not in_speech:
                speech_segments += 1
                in_speech = True
            elif not is_speech and in_speech:
                in_speech = False

        wf.close()
        ratio = (speech_frames / total_frames) if total_frames else 0.0
        return float(ratio), int(speech_segments)
    except Exception:
        return 0.0, 0
    finally:
        cleanup(audio_path)
