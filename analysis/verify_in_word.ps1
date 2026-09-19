# Open the manuscript in real Microsoft Word and assert the APA 7 rules.
#
#   powershell -File analysis/verify_in_word.ps1 <path-to-docx>
#
# LibreOffice is not a substitute for this check. It opened every broken
# package this project produced, including one Word refused outright, so a
# LibreOffice-only pipeline reports success on files the reader cannot open.
param(
    [Parameter(Mandatory=$true)][string]$Path,
    # Figures the sections reference. Word is the only tool here that can say
    # whether they actually LAND on a page: the package can carry every image
    # part with valid relationships and still render blank space, which is how
    # LibreOffice exported this manuscript with four captions and no figures.
    [int]$ExpectFigures = 0,
    # Export the PDF from Word rather than LibreOffice, which drops the images.
    [string]$PdfOut = ""
)

$fail = 0
# Verify a COPY. The real file may be open in the user's own Word, which holds
# a lock, and a verification step must never be the reason a build fails.
$probe = Join-Path $env:TEMP ("apa_verify_" + [guid]::NewGuid().ToString("N") + ".docx")
Copy-Item -LiteralPath $Path -Destination $probe -Force

$w = New-Object -ComObject Word.Application
$w.Visible = $false; $w.DisplayAlerts = 0
try {
    $d = $w.Documents.Open($probe, $false, $true)
} catch {
    Write-Error "FAIL: Word cannot open the file - $($_.Exception.Message.Split([Environment]::NewLine)[0])"
    $w.Quit(); Remove-Item $probe -Force -ErrorAction SilentlyContinue; exit 1
}

$n = $d.Styles("Normal")
function Check($name, $actual, $expected) {
    if ("$actual" -eq "$expected") { "  ok   $name = $actual" }
    else { $script:fail++; "  FAIL $name = $actual (expected $expected)" }
}
"Word opened the document: $($d.ComputeStatistics(2)) pages, $($d.Words.Count) words"
Check "body font"        $n.Font.Name                        "Times New Roman"
Check "body size (pt)"   $n.Font.Size                        12
Check "line spacing"     $n.ParagraphFormat.LineSpacing      24     # double at 12pt
Check "first-line indent" $n.ParagraphFormat.FirstLineIndent 36     # 0.5 inch
Check "alignment"        $n.ParagraphFormat.Alignment        0      # flush left, never justified

$head = $d.Sections(1).Headers(1).Range.Text
if ($head -match "FAKE NEWS") { $script:fail++; "  FAIL running head is still the template sample" }
elseif ($head.Trim().Length -eq 0) { $script:fail++; "  FAIL running head is empty" }
else { "  ok   running head = $($head.Trim())" }

if ($ExpectFigures -gt 0) {
    $shapes = $d.InlineShapes.Count
    if ($shapes -lt $ExpectFigures) {
        $script:fail++
        "  FAIL figures placed = $shapes (expected $ExpectFigures)"
    } else {
        $zero = 0
        foreach ($s in $d.InlineShapes) { if ($s.Width -le 1 -or $s.Height -le 1) { $zero++ } }
        if ($zero -gt 0) { $script:fail++; "  FAIL $zero figure(s) have zero size" }
        else { "  ok   figures placed = $shapes" }
    }
}

# Word's own PDF export (17 = wdExportFormatPDF). LibreOffice's export silently
# omitted every figure from a .docx whose figures Word places correctly, so the
# PDF a reviewer reads must come from the same engine that validates the file.
if ($PdfOut -ne "" -and $fail -eq 0) {
    try {
        $d.ExportAsFixedFormat($PdfOut, 17)
        "  ok   PDF exported from Word"
    } catch {
        $script:fail++
        "  FAIL Word PDF export - $($_.Exception.Message.Split([Environment]::NewLine)[0])"
    }
}

$d.Close($false); $w.Quit()
Remove-Item $probe -Force -ErrorAction SilentlyContinue
if ($fail -gt 0) { Write-Error "$fail APA check(s) failed"; exit 1 }
"all Word-level APA checks passed"
