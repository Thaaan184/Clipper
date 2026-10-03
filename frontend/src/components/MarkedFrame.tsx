import React from "react"

interface MarkedFrameProps {
  children: React.ReactNode
  className?: string
  selected?: boolean
}

export default function MarkedFrame({ children, className = "", selected = false }: MarkedFrameProps) {
  return (
    <div className={`marked-frame ${selected ? "selected" : ""} ${className}`}>
      <i className="crop crop-tl" aria-hidden="true" />
      <i className="crop crop-tr" aria-hidden="true" />
      <i className="crop crop-bl" aria-hidden="true" />
      <i className="crop crop-br" aria-hidden="true" />
      {children}
    </div>
  )
}
