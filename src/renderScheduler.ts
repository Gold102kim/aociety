type RenderClock = {
  now: () => number;
  frame: (callback: FrameRequestCallback) => number;
  cancelFrame: (id: number) => void;
  timer: (callback: () => void, delay: number) => number;
  cancelTimer: (id: number) => void;
};

// One pending callback, even when resize and controls request the same frame.
export function createRenderScheduler(
  render: FrameRequestCallback,
  canRender: () => boolean,
  clock: RenderClock,
  framesPerSecond = 30,
) {
  let frame = 0;
  let timer = 0;
  let lastRender: number | null = null;
  let disposed = false;

  const request = () => {
    if (disposed || !canRender() || frame || timer) return;
    const delay = lastRender === null ? 0 : Math.max(1000 / framesPerSecond - (clock.now() - lastRender), 0);
    const scheduleFrame = () => {
      timer = 0;
      if (disposed || !canRender()) return;
      frame = clock.frame((timestamp) => {
        frame = 0;
        if (disposed || !canRender()) return;
        lastRender = timestamp;
        render(timestamp);
      });
    };
    if (delay > 1) timer = clock.timer(scheduleFrame, delay);
    else scheduleFrame();
  };

  const pause = () => {
    if (frame) clock.cancelFrame(frame);
    if (timer) clock.cancelTimer(timer);
    frame = 0;
    timer = 0;
    lastRender = null;
  };

  return { request, pause, dispose: () => { disposed = true; pause(); } };
}
