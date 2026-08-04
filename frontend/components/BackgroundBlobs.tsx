export default function BackgroundBlobs() {
  return (
    <>
      <div
        style={{
          position: "fixed",
          top: -120,
          left: -110,
          width: 360,
          height: 360,
          borderRadius: "50%",
          background: "radial-gradient(circle, var(--blob1), rgba(0,0,0,0) 70%)",
          filter: "blur(40px)",
          pointerEvents: "none",
          zIndex: 0,
        }}
      />
      <div
        style={{
          position: "fixed",
          bottom: -150,
          right: -130,
          width: 400,
          height: 400,
          borderRadius: "50%",
          background: "radial-gradient(circle, var(--blob2), rgba(0,0,0,0) 70%)",
          filter: "blur(55px)",
          pointerEvents: "none",
          zIndex: 0,
        }}
      />
      <div
        style={{
          position: "fixed",
          top: "38%",
          right: -170,
          width: 320,
          height: 320,
          borderRadius: "50%",
          background: "radial-gradient(circle, var(--blob3), rgba(0,0,0,0) 70%)",
          filter: "blur(50px)",
          pointerEvents: "none",
          zIndex: 0,
        }}
      />
    </>
  );
}
