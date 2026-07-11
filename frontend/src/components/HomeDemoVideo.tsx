import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

type HomeDemoVideoProps = {
  src: string;
  title: string;
};

/**
 * Muted looping demo clip with no native controls.
 * Click expands in-place over a light backdrop; click again (or Escape) collapses.
 */
export default function HomeDemoVideo({ src, title }: HomeDemoVideoProps) {
  const [expanded, setExpanded] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const labelId = useId();

  useEffect(() => {
    if (!expanded) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setExpanded(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [expanded]);

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    void Promise.resolve(el.play()).catch(() => {
      /* autoplay may be blocked; muted + playsInline usually ok */
    });
  }, [expanded, src]);

  function toggle() {
    setExpanded((v) => !v);
  }

  return (
    <div>
      <h3 id={labelId} className="text-sm font-medium text-gray-800">
        {title}
      </h3>
      <div className="relative mt-3 aspect-video w-full overflow-hidden rounded-xl">
        {!expanded ? (
          <video
            ref={videoRef}
            src={src}
            className="block h-full w-full cursor-pointer rounded-xl bg-gray-900 object-cover shadow-sm transition-transform duration-300 ease-out hover:scale-[1.01]"
            autoPlay
            muted
            loop
            playsInline
            controls={false}
            disablePictureInPicture
            onClick={toggle}
            aria-labelledby={labelId}
          />
        ) : (
          <div className="h-full w-full rounded-xl bg-gray-200/80" aria-hidden />
        )}
      </div>

      {expanded
        ? createPortal(
            <div
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 transition-opacity duration-300 sm:p-8"
              role="dialog"
              aria-modal="true"
              aria-labelledby={labelId}
              onClick={() => setExpanded(false)}
            >
              <div
                className="w-full max-w-4xl scale-100 transition-transform duration-300 ease-out"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="aspect-video w-full overflow-hidden rounded-2xl shadow-2xl ring-1 ring-white/20">
                  <video
                    ref={videoRef}
                    src={src}
                    className="block h-full w-full cursor-pointer bg-gray-900 object-cover"
                    autoPlay
                    muted
                    loop
                    playsInline
                    controls={false}
                    disablePictureInPicture
                    onClick={toggle}
                    aria-labelledby={labelId}
                  />
                </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}
