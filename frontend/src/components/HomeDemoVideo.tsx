import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

type HomeDemoVideoProps = {
  src: string;
  title: string;
};

type Box = { top: number; left: number; width: number; height: number };

const ZOOM_MS = 380;

function coverBox(): Box {
  const pad = 20;
  const maxW = window.innerWidth - pad * 2;
  const maxH = window.innerHeight - pad * 2;
  let width = maxW;
  let height = (width * 9) / 16;
  if (height > maxH) {
    height = maxH;
    width = (height * 16) / 9;
  }
  return {
    left: (window.innerWidth - width) / 2,
    top: (window.innerHeight - height) / 2,
    width,
    height,
  };
}

/**
 * Muted looping demo clip. Click zooms from thumbnail to near-fullscreen (FLIP scale);
 * click again (or Escape) zooms back.
 */
export default function HomeDemoVideo({ src, title }: HomeDemoVideoProps) {
  const [phase, setPhase] = useState<"idle" | "opening" | "open" | "closing">("idle");
  const [origin, setOrigin] = useState<Box | null>(null);
  const [frame, setFrame] = useState<Box | null>(null);

  const thumbWrapRef = useRef<HTMLDivElement>(null);
  const thumbVideoRef = useRef<HTMLVideoElement>(null);
  const overlayVideoRef = useRef<HTMLVideoElement>(null);
  const savedTimeRef = useRef(0);
  const labelId = useId();

  const active = phase !== "idle";

  useEffect(() => {
    if (!active) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") closeZoom();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  useLayoutEffect(() => {
    if (phase !== "opening" || !origin) return;
    setFrame(origin);
    const id = requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        setFrame(coverBox());
        setPhase("open");
      });
    });
    return () => cancelAnimationFrame(id);
  }, [phase, origin]);

  useEffect(() => {
    const el = active ? overlayVideoRef.current : thumbVideoRef.current;
    if (!el) return;
    void Promise.resolve(el.play()).catch(() => {});
  }, [active, src, phase]);

  function openZoom() {
    const wrap = thumbWrapRef.current;
    const thumb = thumbVideoRef.current;
    if (!wrap) return;
    const r = wrap.getBoundingClientRect();
    savedTimeRef.current = thumb?.currentTime ?? 0;
    const box = { top: r.top, left: r.left, width: r.width, height: r.height };
    setOrigin(box);
    setFrame(box);
    setPhase("opening");
  }

  function closeZoom() {
    if (phase !== "open" && phase !== "opening") return;
    const wrap = thumbWrapRef.current;
    const overlay = overlayVideoRef.current;
    if (overlay) savedTimeRef.current = overlay.currentTime;
    const back = wrap
      ? (() => {
          const r = wrap.getBoundingClientRect();
          return { top: r.top, left: r.left, width: r.width, height: r.height };
        })()
      : origin;
    if (back) setFrame(back);
    setPhase("closing");
    window.setTimeout(() => {
      setPhase("idle");
      setOrigin(null);
      setFrame(null);
      const thumb = thumbVideoRef.current;
      if (thumb) {
        thumb.currentTime = savedTimeRef.current;
        void Promise.resolve(thumb.play()).catch(() => {});
      }
    }, ZOOM_MS);
  }

  function onOverlayVideoReady() {
    const el = overlayVideoRef.current;
    if (!el) return;
    el.currentTime = savedTimeRef.current;
    void Promise.resolve(el.play()).catch(() => {});
  }

  return (
    <div>
      <h3 id={labelId} className="text-lg font-semibold text-gray-900">
        {title}
      </h3>
      <div
        ref={thumbWrapRef}
        className="relative mt-3 aspect-video w-full overflow-hidden rounded-xl"
      >
        <video
          ref={thumbVideoRef}
          src={src}
          className={`block h-full w-full cursor-pointer rounded-xl bg-gray-900 object-cover shadow-sm ${
            active ? "invisible" : "hover:scale-[1.01] transition-transform duration-300"
          }`}
          autoPlay
          muted
          loop
          playsInline
          controls={false}
          disablePictureInPicture
          onClick={openZoom}
          aria-labelledby={labelId}
        />
        {active ? <div className="absolute inset-0 rounded-xl bg-gray-200/70" aria-hidden /> : null}
      </div>

      {active && frame
        ? createPortal(
            <>
              <div
                className="fixed inset-0 z-50 bg-black/45 transition-opacity"
                style={{
                  opacity: phase === "open" ? 1 : 0,
                  transitionDuration: `${ZOOM_MS}ms`,
                }}
                aria-hidden
                onClick={closeZoom}
              />
              <div
                role="dialog"
                aria-modal="true"
                aria-labelledby={labelId}
                className="fixed z-[51] overflow-hidden bg-black shadow-2xl"
                style={{
                  top: frame.top,
                  left: frame.left,
                  width: frame.width,
                  height: frame.height,
                  borderRadius: phase === "open" ? 16 : 12,
                  transitionProperty: "top, left, width, height, border-radius",
                  transitionDuration: `${ZOOM_MS}ms`,
                  transitionTimingFunction: "cubic-bezier(0.22, 1, 0.36, 1)",
                }}
              >
                <video
                  ref={overlayVideoRef}
                  src={src}
                  className="block h-full w-full cursor-pointer object-cover"
                  muted
                  loop
                  playsInline
                  controls={false}
                  disablePictureInPicture
                  onLoadedData={onOverlayVideoReady}
                  onClick={closeZoom}
                  aria-labelledby={labelId}
                />
              </div>
            </>,
            document.body,
          )
        : null}
    </div>
  );
}
