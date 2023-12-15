you can decode audio files from mdk2 (original) using ffmpeg
after extracting the zips, rename all files to acm extension
(so ffmpeg picks up the correct format)
then convert with skipping the first 28 bytes which are custom header for mdk2
```
ffmpeg --skip_initial_bytes 28  -i input.acm ouput.wav
```

(change input.acm and output.wav to actual names)

the game can read the decoded files directly, just put the modified files in override directory
