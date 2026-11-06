import { keys, readJSON, writeJSON } from "./storage";

/** 발급 연출의 효과음. 어떤 호출도 예외를 밖으로 내보내지 않아서, 재생에 실패해도 화면은 그대로 흐른다. */
export interface IssueSound {
  paper(): void;
  clause(): void;
  stamp(): void;
  branch(): void;
}

export const SILENT: IssueSound = { paper() {}, clause() {}, stamp() {}, branch() {} };

export function soundEnabled(): boolean {
  return readJSON<boolean>("local", keys.sound) === true;
}

export function setSoundEnabled(on: boolean): void {
  writeJSON("local", keys.sound, on);
}

type AudioCtor = typeof AudioContext;
let ctx: AudioContext | null = null;

/**
 * 사용자가 누른 순간에 불러야 브라우저가 소리를 허용한다.
 * ambient는 기기의 무음 설정을 따르게 하는 Safari 설정이고, 지원하지 않으면 무시된다.
 */
export function unlockSound(): void {
  if (!soundEnabled()) return;
  try {
    const session = (navigator as Navigator & { audioSession?: { type: string } }).audioSession;
    if (session) session.type = "ambient";
    const Ctor = (window.AudioContext ?? (window as unknown as { webkitAudioContext?: AudioCtor }).webkitAudioContext) as
      | AudioCtor
      | undefined;
    if (!Ctor) return;
    ctx ??= new Ctor();
    void ctx.resume().catch(() => {});
  } catch {
    ctx = null;
  }
}

function tone(c: AudioContext, from: number, to: number, seconds: number, volume: number, at = 0) {
  const start = c.currentTime + at;
  const osc = c.createOscillator();
  const gain = c.createGain();
  osc.frequency.setValueAtTime(from, start);
  osc.frequency.exponentialRampToValueAtTime(to, start + seconds);
  gain.gain.setValueAtTime(volume, start);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + seconds);
  osc.connect(gain).connect(c.destination);
  osc.start(start);
  osc.stop(start + seconds);
}

function noise(c: AudioContext, seconds: number, volume: number, cutoff: number) {
  const frames = Math.floor(c.sampleRate * seconds);
  const buffer = c.createBuffer(1, frames, c.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < frames; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / frames);
  const src = c.createBufferSource();
  const filter = c.createBiquadFilter();
  const gain = c.createGain();
  src.buffer = buffer;
  filter.type = "lowpass";
  filter.frequency.value = cutoff;
  gain.gain.value = volume;
  src.connect(filter).connect(gain).connect(c.destination);
  src.start();
}

function guarded(fn: (c: AudioContext) => void): () => void {
  return () => {
    try {
      if (ctx && ctx.state === "running") fn(ctx);
    } catch {
      /* 소리 없이 계속한다 */
    }
  };
}

const PLAYING: IssueSound = {
  paper: guarded((c) => noise(c, 0.45, 0.05, 1800)),
  clause: guarded((c) => tone(c, 520, 420, 0.06, 0.025)),
  stamp: guarded((c) => {
    tone(c, 130, 55, 0.16, 0.12);
    noise(c, 0.05, 0.06, 900);
  }),
  branch: guarded((c) => {
    tone(c, 784, 784, 0.25, 0.018, 0.1);
    tone(c, 988, 988, 0.3, 0.015, 0.22);
  }),
};

/** 사용자가 직접 연 연출에서, 효과음을 켠 경우에만 소리를 낸다. */
export function issueSoundFor(started: boolean): IssueSound {
  return started && soundEnabled() ? PLAYING : SILENT;
}
