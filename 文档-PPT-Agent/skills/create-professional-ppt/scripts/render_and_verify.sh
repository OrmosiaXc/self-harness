#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -lt 2 ]]; then
  echo "用法：$0 <pptx> <空输出目录> [预期页数] [标题文件]" >&2
  exit 2
fi

pptx_path="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
output_dir="$2"
expected_slides="${3:-}"
expected_titles="${4:-}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
validator="${script_dir}/validate_editable_pptx.py"
overview_script="${script_dir}/make_qa_overviews.py"
python_runtime="${PPT_PYTHON_RUNTIME:-python3}"
pdftoppm_runtime="${PPT_PDFTOPPM_RUNTIME:-pdftoppm}"
soffice_runtime="${PPT_SOFFICE_RUNTIME:-soffice}"

if [[ ! -f "${pptx_path}" ]]; then
  echo "PPTX 不存在：${pptx_path}" >&2
  exit 2
fi

mkdir -p "${output_dir}"
if find "${output_dir}" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
  echo "输出目录必须为空：${output_dir}" >&2
  exit 2
fi

output_dir_absolute="$(cd "${output_dir}" && pwd)"
soffice_profile="${output_dir_absolute}/.soffice-profile"
mkdir -p "${soffice_profile}"
"${soffice_runtime}" \
  "-env:UserInstallation=file://${soffice_profile}" \
  --headless --convert-to pdf --outdir "${output_dir}" "${pptx_path}"
pdf_path="${output_dir}/$(basename "${pptx_path%.*}").pdf"
if [[ ! -f "${pdf_path}" ]]; then
  echo "LibreOffice 未生成预期 PDF：${pdf_path}" >&2
  exit 1
fi

"${pdftoppm_runtime}" -png -r 144 "${pdf_path}" "${output_dir}/slide"
"${python_runtime}" "${overview_script}" "${output_dir}" "${output_dir}"

validator_args=(
  "${validator}"
  "${pptx_path}"
  --json "${output_dir}/pptx_structure_report.json"
  --markdown "${output_dir}/PPTX结构验证报告.md"
)
if [[ -n "${expected_slides}" ]]; then
  validator_args+=(--expected-slides "${expected_slides}")
fi
if [[ -n "${expected_titles}" ]]; then
  validator_args+=(--expected-titles "${expected_titles}")
fi
"${python_runtime}" "${validator_args[@]}"

echo "渲染与结构验证完成：${output_dir}"
