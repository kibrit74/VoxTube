// main.js
document.addEventListener('DOMContentLoaded', function() {
    let player;
    let audioPlayer;
    let segments = [];
    let isPlaying = false;
    let isTranslationStarted = false;
    let syncOffset = 0;

    const form = document.getElementById('translationForm');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const resultContainer = document.getElementById('result');
    const errorMessage = document.getElementById('errorMessage');
    const successMessage = document.getElementById('successMessage');
    const playButton = document.getElementById('playButton');
    const pauseButton = document.getElementById('pauseButton');
    const volumeControl = document.getElementById('volumeControl');
    const syncControl = document.getElementById('syncControl');
    const syncValue = document.getElementById('syncValue');
    const subtitlesContainer = document.getElementById('subtitlesContainer');
    const audioStatus = document.getElementById('audioStatus');

    // Web Worker oluşturma
    const worker = new Worker('worker.js');

    worker.onmessage = function(e) {
        const { type, data } = e.data;
        switch (type) {
            case 'translationComplete':
                hideLoading();
                showSuccess('Çeviri başarıyla tamamlandı!');
                initializePlayer(data.video_id, data.audio_data, data.segments);
                break;
            case 'error':
                hideLoading();
                showError(data.message);
                break;
        }
    };

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        showLoading();
        worker.postMessage({
            type: 'startTranslation',
            data: Object.fromEntries(formData)
        });
    });

    function initializePlayer(videoId, audioData, translatedSegments) {
        segments = translatedSegments;
        const videoContainer = document.getElementById('videoContainer');
        videoContainer.innerHTML = `<div id="youtubeVideo"></div>`;
        
        player = new YT.Player('youtubeVideo', {
            height: '360',
            width: '640',
            videoId: videoId,
            events: {
                'onReady': () => onPlayerReady(audioData),
                'onStateChange': onPlayerStateChange
            }
        });

        resultContainer.style.display = 'block';
    }

    function onPlayerReady(audioData) {
        const audioBlob = base64ToBlob(audioData, 'audio/mpeg');
        audioPlayer = new Audio(URL.createObjectURL(audioBlob));
        
        audioPlayer.addEventListener('loadeddata', () => {
            audioStatus.textContent = 'Ses dosyası yüklendi';
            isTranslationStarted = true;
            showControls();
        });

        audioPlayer.addEventListener('error', (e) => {
            console.error('Ses dosyası yüklenirken hata oluştu:', e);
            audioStatus.textContent = 'Ses dosyası yüklenemedi: ' + e.message;
        });
    }

    function onPlayerStateChange(event) {
        if (event.data == YT.PlayerState.PLAYING) {
            if (!isPlaying) {
                audioPlayer.play();
                isPlaying = true;
            }
        } else if (event.data == YT.PlayerState.PAUSED) {
            audioPlayer.pause();
            isPlaying = false;
        }
    }

    function showControls() {
        document.getElementById('controls').style.display = 'flex';
    }

    playButton.addEventListener('click', function() {
        if (isTranslationStarted && player && audioPlayer) {
            player.playVideo();
            audioPlayer.currentTime = player.getCurrentTime() + syncOffset;
            audioPlayer.play();
            isPlaying = true;
        } else {
            showError("Çeviri henüz hazır değil. Lütfen bekleyin.");
        }
    });

    pauseButton.addEventListener('click', function() {
        if (player && audioPlayer) {
            player.pauseVideo();
            audioPlayer.pause();
            isPlaying = false;
        }
    });

    setInterval(function() {
        if (isPlaying && player && audioPlayer) {
            const videoCurrentTime = player.getCurrentTime();
            const timeDiff = Math.abs(videoCurrentTime - (audioPlayer.currentTime - syncOffset));
            if (timeDiff > 0.5) {
                audioPlayer.currentTime = videoCurrentTime + syncOffset;
            }
            updateSubtitles(videoCurrentTime);
        }
    }, 100);

    volumeControl.addEventListener('input', function(e) {
        if (audioPlayer) {
            audioPlayer.volume = e.target.value;
        }
    });

    syncControl.addEventListener('input', function(e) {
        syncOffset = parseFloat(e.target.value);
        syncValue.textContent = syncOffset.toFixed(1);
        if (isPlaying && player && audioPlayer) {
            audioPlayer.currentTime = player.getCurrentTime() + syncOffset;
        }
    });

    function updateSubtitles(currentTime) {
        let currentSegment = segments.find(seg => seg.start <= currentTime && seg.end > currentTime);
        if (currentSegment) {
            subtitlesContainer.textContent = currentSegment.text;
            subtitlesContainer.setAttribute('aria-label', `Altyazı: ${currentSegment.text}`);
        } else {
            subtitlesContainer.textContent = '';
            subtitlesContainer.setAttribute('aria-label', 'Altyazı yok');
        }
    }

    function base64ToBlob(base64, mimeType) {
        const byteCharacters = atob(base64);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        return new Blob([byteArray], {type: mimeType});
    }

    function showLoading() {
        loadingIndicator.style.display = 'block';
        form.style.display = 'none';
    }

    function hideLoading() {
        loadingIndicator.style.display = 'none';
    }

    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.style.display = 'block';
        errorMessage.classList.add('fade-in');
        setTimeout(() => {
            errorMessage.classList.remove('fade-in');
            errorMessage.style.display = 'none';
        }, 5000);
    }

    function showSuccess(message) {
        successMessage.textContent = message;
        successMessage.style.display = 'block';
        successMessage.classList.add('fade-in');
        setTimeout(() => {
            successMessage.classList.remove('fade-in');
            successMessage.style.display = 'none';
        }, 3000);
    }
});
