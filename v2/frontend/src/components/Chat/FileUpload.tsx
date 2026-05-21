import { useCallback } from 'react'
import { Upload } from 'lucide-react'

interface Props {
  onFiles: (files: File[]) => void
}

export function FileUpload({ onFiles }: Props) {
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const files = Array.from(e.dataTransfer.files)
    if (files.length) onFiles(files)
  }, [onFiles])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
  }, [])

  return (
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      className="mx-4 my-2 border-2 border-dashed border-white/10 rounded-xl p-6 text-center hover:border-primary/30 transition cursor-pointer"
    >
      <Upload size={24} className="mx-auto mb-2 text-gray-500" />
      <p className="text-sm text-gray-500">Kéo file vào đây hoặc click để upload</p>
    </div>
  )
}
