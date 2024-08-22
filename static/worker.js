// worker.js
self.onmessage = async function(e) {
    if (e.data.type === 'startTranslation') {
        try {
            const response = await fetch('/translate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(e.data.data)
            });
            
            if (!response.ok) {
                throw new Error('Çeviri işlemi başarısız oldu');
            }
            
            const data = await response.json();
            
            if (!data.audio_data) {
                throw new Error('Ses dosyası oluşturulamadı');
            }
            
            self.postMessage({ type: 'translationComplete', data });
        } catch (error) {
            self.postMessage({ type: 'error', data: { message: error.message } });
        }
    }
};
