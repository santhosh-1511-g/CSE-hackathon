try:
    from moviepy.config import get_setting
    print(f"MoviePy FFmpeg binary path: {get_setting('FFMPEG_BINARY')}")
except Exception as e:
    print(f"Error checking settings: {e}")

try:
    import imageio_ffmpeg
    print(f"Imageio-FFmpeg path: {imageio_ffmpeg.get_ffmpeg_exe()}")
except Exception as e:
    print(f"Error checking imageio: {e}")
