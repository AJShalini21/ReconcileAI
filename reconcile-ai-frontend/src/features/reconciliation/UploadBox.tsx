import { useRef } from "react"
import { Button } from "../../components/ui/Button"
import { Icon } from "../../components/ui/Icon"

export function UploadBox({
  label,
  file,
  onFile,
}: {
  label: string
  file?: File
  onFile: (file?: File) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <div className={`upload-box ${file ? "upload-box--ready" : ""}`}>
      <input
        accept=".csv,text/csv"
        aria-label={label}
        className="sr-only"
        onChange={(event) => onFile(event.target.files?.[0])}
        ref={inputRef}
        type="file"
      />
      <span className="upload-box__icon">
        <Icon name={file ? "file" : "upload"} size={22} />
      </span>
      <div>
        <strong>{file ? file.name : label}</strong>
        <p>
          {file
            ? `${Math.max(1, Math.round(file.size / 1024))} KB · Ready to process`
            : "Drag and drop your CSV here, or choose a file"}
        </p>
      </div>
      <Button onClick={() => inputRef.current?.click()}>
        {file ? "Replace file" : "Choose file"}
      </Button>
    </div>
  )
}
