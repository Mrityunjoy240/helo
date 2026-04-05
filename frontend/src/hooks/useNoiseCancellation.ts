import { useRef, useCallback } from 'react';

interface NoiseCancellationOptions {
    enabled: boolean;
    noiseGateThreshold?: number; // -60 to 0 dB
    highPassFrequency?: number; // Hz (removes low-frequency noise)
    noiseReduction?: number; // 0 to 1 (0 = no reduction, 1 = maximum)
}

interface UseNoiseCancellationReturn {
    processAudio: (audioStream: MediaStream) => MediaStream | null;
    cleanup: () => void;
}

/**
 * Custom hook for noise cancellation using Web Audio API
 * Applies noise gate, high-pass filter, and noise reduction
 */
export const useNoiseCancellation = (
    options: NoiseCancellationOptions
): UseNoiseCancellationReturn => {
    const audioContextRef = useRef<AudioContext | null>(null);
    const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
    const destinationNodeRef = useRef<MediaStreamAudioDestinationNode | null>(null);
    const gainNodeRef = useRef<GainNode | null>(null);
    const highPassFilterRef = useRef<BiquadFilterNode | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);

    const processAudio = useCallback(
        (audioStream: MediaStream): MediaStream | null => {
            if (!options.enabled) {
                return audioStream;
            }

            try {
                // Create AudioContext if it doesn't exist
                if (!audioContextRef.current) {
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
                }

                const audioContext = audioContextRef.current;

                // Create source from input stream
                sourceNodeRef.current = audioContext.createMediaStreamSource(audioStream);

                // Create destination for processed audio
                destinationNodeRef.current = audioContext.createMediaStreamDestination();

                // Create gain node for noise gate
                gainNodeRef.current = audioContext.createGain();
                gainNodeRef.current.gain.value = 1.0;

                // Create high-pass filter to remove low-frequency noise (like fan noise, AC hum)
                highPassFilterRef.current = audioContext.createBiquadFilter();
                highPassFilterRef.current.type = 'highpass';
                highPassFilterRef.current.frequency.value = options.highPassFrequency || 80; // Default 80Hz
                highPassFilterRef.current.Q.value = 1;

                // Create analyser for noise gate (detects audio level)
                analyserRef.current = audioContext.createAnalyser();
                analyserRef.current.fftSize = 256;
                analyserRef.current.smoothingTimeConstant = 0.8;

                // Connect nodes: Source -> High-pass Filter -> Analyser -> Gain -> Destination
                sourceNodeRef.current.connect(highPassFilterRef.current);
                highPassFilterRef.current.connect(analyserRef.current);
                analyserRef.current.connect(gainNodeRef.current);
                gainNodeRef.current.connect(destinationNodeRef.current);

                // Noise gate implementation
                const noiseGateThreshold = options.noiseGateThreshold || -45; // Default -45 dB
                const noiseReduction = options.noiseReduction || 0.3; // Default 30% reduction
                const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);

                const applyNoiseGate = () => {
                    if (!analyserRef.current || !gainNodeRef.current) return;

                    analyserRef.current.getByteFrequencyData(dataArray);

                    // Calculate average amplitude
                    let sum = 0;
                    for (let i = 0; i < dataArray.length; i++) {
                        sum += dataArray[i];
                    }
                    const average = sum / dataArray.length;

                    // Convert to dB (0-255 range to dB)
                    const db = 20 * Math.log10(average / 255);

                    // Apply noise gate: reduce gain when below threshold
                    if (db < noiseGateThreshold) {
                        // Gradually reduce gain for noise
                        const reductionFactor = Math.max(0, 1 - noiseReduction);
                        gainNodeRef.current.gain.setTargetAtTime(
                            reductionFactor,
                            audioContext.currentTime,
                            0.01 // Smooth transition
                        );
                    } else {
                        // Restore full gain for speech
                        gainNodeRef.current.gain.setTargetAtTime(
                            1.0,
                            audioContext.currentTime,
                            0.01
                        );
                    }

                    // Continue monitoring
                    requestAnimationFrame(applyNoiseGate);
                };

                applyNoiseGate();

                // Return processed stream
                return destinationNodeRef.current.stream;
            } catch (error) {
                console.error('Noise cancellation error:', error);
                // Fallback to original stream if processing fails
                return audioStream;
            }
        },
        [options.enabled, options.noiseGateThreshold, options.highPassFrequency, options.noiseReduction]
    );

    const cleanup = useCallback(() => {
        // Disconnect all nodes
        if (sourceNodeRef.current) {
            try {
                sourceNodeRef.current.disconnect();
            } catch (e) {
                // Already disconnected
            }
            sourceNodeRef.current = null;
        }

        if (highPassFilterRef.current) {
            try {
                highPassFilterRef.current.disconnect();
            } catch (e) {
                // Already disconnected
            }
            highPassFilterRef.current = null;
        }

        if (gainNodeRef.current) {
            try {
                gainNodeRef.current.disconnect();
            } catch (e) {
                // Already disconnected
            }
            gainNodeRef.current = null;
        }

        if (analyserRef.current) {
            try {
                analyserRef.current.disconnect();
            } catch (e) {
                // Already disconnected
            }
            analyserRef.current = null;
        }

        if (destinationNodeRef.current) {
            try {
                destinationNodeRef.current.disconnect();
            } catch (e) {
                // Already disconnected
            }
            destinationNodeRef.current = null;
        }

        // Close audio context
        if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
            audioContextRef.current.close().catch(console.error);
            audioContextRef.current = null;
        }
    }, []);

    return {
        processAudio,
        cleanup
    };
};

