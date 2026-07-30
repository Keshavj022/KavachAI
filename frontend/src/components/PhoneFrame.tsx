/**
 * Device bezel wrapper so the consumer app reads as a phone on a laptop or
 * projector. The interrupt takeover is rendered inside this frame, so the
 * `relative` + `overflow-hidden` here is what clips it to the screen.
 */
export default function PhoneFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-full items-center justify-center bg-slate-100 px-4 py-6">
      <div className="relative h-[780px] w-[380px] max-w-full rounded-[2.75rem] border-[10px] border-slate-900 bg-black shadow-phone">
        {/* Notch */}
        <div className="absolute left-1/2 top-0 z-30 h-6 w-36 -translate-x-1/2 rounded-b-2xl bg-slate-900" />
        {/* Screen */}
        <div className="relative h-full w-full overflow-hidden rounded-[2rem] bg-consumer-bg">
          {children}
        </div>
      </div>
    </div>
  );
}
