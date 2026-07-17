# Aociety Unreal C++ Class Headers

This folder contains all the C++ header and source files for the Aociety UE5 module.

## Module Structure

- `Aociety.h/cpp` - Module entry point
- `AocietyClientSubsystem.h/cpp` - GameInstanceSubsystem that handles HTTP/WS communication with backend
- `CameraCaptureComponent.h/cpp` - ActorComponent that captures frames from camera
- `MicCaptureComponent.h/cpp` - ActorComponent that captures audio from microphone
- `TTSPlayer.h/cpp` - Utility component for playing sweet-voice TTS audio

## Quick Start

```cpp
// Get subsystem from anywhere
UAocietyClientSubsystem* Client = GetGameInstance()->GetSubsystem<UAocietyClientSubsystem>();
if (Client && !Client->IsConnected()) Client->Connect();

// Subscribe to events
Client->OnEmotionUpdated.AddDynamic(this, &AMyClass::HandleEmotion);
Client->OnCareTriggered.AddDynamic(this, &AMyClass::HandleCare);
Client->OnTTSReady.AddDynamic(this, &AMyClass::PlaySweetVoice);

// Send data
Client->PushCameraFrame(JPEGBytes);
Client->PushAudioChunk(PCM16Bytes);
Client->PushTextHint("I'm feeling sad today");

// Trigger NPC care (manual or auto)
Client->RequestNPCCare("npc_01");
```
