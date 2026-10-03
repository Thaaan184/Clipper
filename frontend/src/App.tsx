import React from "react"
import { Routes, Route } from "react-router-dom"
import Header from "@/components/Header"
import Home from "@/pages/Home"
import Processing from "@/pages/Processing"
import Results from "@/pages/Results"

export default function App() {
  return (
    <div style={{ minHeight: "100vh", background: "#0A0A0A", color: "#F5F5F5" }}>
      <Header />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/processing/:jobId/:videoId" element={<Processing />} />
        <Route path="/results/:videoId" element={<Results />} />
      </Routes>
      <footer
        style={{
          height: 60,
          padding: "0 4vw",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderTop: "1px solid #2A2A2A",
          color: "#444",
          fontSize: 11,
          letterSpacing: "0.12em",
        }}
      >
        <span>CLIPFORGE / CUT WHAT MATTERS</span>
        <span>JAKARTA — ID</span>
      </footer>
    </div>
  )
}
