# PROJECT BLUEPRINT: THE STUDIO (Reusable Open-Backlot Film Studio)

> **Quyền sở hữu & Cơ chế vận hành:** Dự án này được bàn giao trọn gói cho **Claude Code** đóng vai trò **Tổng Thầu Tự Trị (Autonomous Principal Architect & Builder)**. Chủ dự án giữ vai trò **Executive Producer** — không trực tiếp viết code, không vẽ tay, không can thiệp quy trình kỹ thuật trung gian. Claude chịu trách nhiệm toàn trình: kiến trúc, tích hợp repo/asset mở, xây dựng hệ thống Sub-Agent, tự kiểm thử đầu-cuối (End-to-End QA), và bàn giao sản phẩm hoàn thiện trên **Git repository cá nhân** để tái sử dụng cho nhiều dự án nội dung khác nhau.

---

## 1. Định Nghĩa Sản Phẩm & Định Hướng Mỹ Thuật (Product & Art Vision)
- **Tên sản phẩm:** `THE STUDIO` — Hệ thống Phim Trường Mở (Open-Backlot) tự động hóa đa tác nhân, chạy cục bộ trên GPU.
- **Gu thẩm mỹ mục tiêu (Western Narrative Animation):** Hướng tới ngôn ngữ thị giác thân thiện với văn hóa phương Tây hiện đại (tham chiếu chất lượng kể chuyện, biểu cảm và nhịp dựng của *Ifnation* và *Giáo Sư Bút*):
  - Nhân vật có tỷ lệ giải phẫu chuẩn, bàn tay có ngón diễn xuất, nét mặt giàu cảm xúc và ngôn ngữ cơ thể (body language) mượt mà, tự nhiên.
  - Phim trường 3D có chiều sâu ánh sáng điện ảnh nhưng được đồng bộ hóa bằng phong cách **2.5D Stylized Toon + Nét mực thanh đậm (Line Art)** để tạo cảm giác gần gũi, nghệ thuật.
  - Hòa quyện mượt mà giữa cảnh diễn xuất nhân vật và các **Motion Graphic Elements** (thẻ thông tin, biểu đồ, icon nảy nhịp, typography nhấn ý).
- **Triết lý kỹ thuật bắt buộc:**
  1. **Zero-Drawing / Asset-First:** Không vẽ nhân vật bằng code hình học thô sơ. Tận dụng tối đa hệ sinh thái Open-Source, CC0 Assets, Parametric Character Generators và MoCap có sẵn, rồi đồng bộ hóa tất cả bằng một bộ **Master Look-Dev Shader** duy nhất.
  2. **Token-Minimal, GPU-Maximal:** Tách biệt hoàn toàn khâu Đạo diễn (AI chỉ xuất file cấu hình JSON nhẹ) khỏi khâu Dựng hình & Render (100% chạy bằng Python/GPU tại máy, tốn 0 token API).
  3. **Portable & Reusable Git Product:** Được đóng gói như một công cụ độc lập trên Git cá nhân; mọi dự án video tương lai chỉ cần gắn kịch bản + voice là vận hành được ngay.

---

## 2. Kiến Trúc Công Nghệ & Kho Tài Nguyên Mở (Core Tech Stack)
Toàn bộ hệ thống vận hành theo mô hình **Dual-Engine Hybrid**:

| Thành Phần | Công Nghệ / Repo / Nguồn Free | Chức Năng Trong The Studio |
| :--- | :--- | :--- |
| **Lõi Phim Trường & GPU Render** | **Blender 4.x (EEVEE Next + Grease Pencil Line Art)** | Dựng bối cảnh 3D, chiếu sáng điện ảnh, bọc viền mực 2D tự động và render tốc độ cao trực tiếp trên GPU (CUDA/OptiX/Vulkan). |
| **Cầu Nối Tự Động Hóa AI** | **`ahujasid/blender-mcp`** + **Blender Headless Python (`bpy`)** | Claude dựng set/nhân vật mẫu qua MCP và tự động hóa sản xuất hàng loạt bằng script Python không giao diện (0 token). |
| **Đúc Diễn Viên Đa Dạng** | **`makehumancommunity/mpfb2`** + **Blender Studio Open Movie Rigs** | Sinh diễn viên đa sắc tộc, mọi độ tuổi, vóc dáng, phong cách trang phục theo tham số JSON, có sẵn xương mặt & Rigify. |
| **Ngôn Ngữ Cơ Thể (Body Language)** | **Adobe Mixamo (Free)** + **CMU MoCap Database** | Thư viện hành động mượt mà đóng gói dạng **NLA Action Library** (tranh luận, gục bàn, lướt điện thoại, ngạc nhiên, đi lại...). |
| **Khớp Khẩu Hình Tự Động** | **`DanielSWolf/rhubarb-lip-sync`** + **`scaredyfish/blender-rhubarb-lipsync`** | Tự động phân tích file audio giọng đọc thành chuỗi khẩu hình khớp chính xác từng âm tiết lên mặt nhân vật. |
| **Phim Trường & Đạo Cụ Mở** | **Poly Haven (CC0)**, **Quaternius (CC0)**, **BlenderKit (Free)** | Kho kiến trúc, nội thất, đường phố, văn phòng, quán cà phê và ánh sáng môi trường HDRI miễn phí bản quyền thương mại. |
| **Elements Đồ Họa & Hậu Kỳ** | **Remotion / HTML5 + GSAP** + **FFmpeg** | Xuất lớp thẻ minh họa, biểu đồ, icon và phụ đề nền trong suốt (Alpha), sau đó trộn siêu tốc với lớp video Blender + Audio. |

---

## 3. Bộ Máy Sản Xuất: Hệ Thống 5 Sub-Agents Chuyên Biệt
Toàn bộ năng lực của `THE STUDIO` được chia nhỏ thành 5 Sub-Agent độc lập nằm trong `.claude/agents/`, mỗi phòng ban sở hữu bộ Skills, Presets và Scripts riêng để chuyên môn hóa tối đa và tránh lãng phí ngữ cảnh:

1. **`01-showrunner` (Tổng Đạo Diễn & Nhịp Dựng):**
   - *Kỹ năng:* `skill-story-pacing.md`, `skill-western-visual-language.md`.
   - *Nhiệm vụ:* Đọc kịch bản + file timing audio và danh mục `catalog_manifest.json` để biên dịch thành duy nhất 1 file chỉ đạo `episode_shotlist.json` (chọn bối cảnh, diễn viên, cảm xúc, động tác, góc máy và điểm nổ thẻ đồ họa). Tuyệt đối không viết code 3D.
2. **`02-casting` (Phòng Đúc Diễn Viên & Tạo Hình):**
   - *Kỹ năng:* `skill-character-lookdev.md`, API của `MPFB2`.
   - *Nhiệm vụ:* Tạo mới và chuẩn hóa diễn viên đa chủng tộc/tuổi tác/vibe; tự động bọc `Master_Toon_Shader`, gắn hệ xương tương thích MoCap/Lip-Sync và lưu vào kho `/asset_vault/actors/`.
3. **`03-set-designer` (Phòng Thiết Kế Bối Cảnh & Ánh Sáng):**
   - *Kỹ năng:* `skill-set-dressing.md`, `blender-mcp` (Poly Haven/Quaternius).
   - *Nhiệm vụ:* Lắp ghép các phim trường mở có thể tùy biến linh hoạt concept (ánh sáng sáng/trưa/tối/kịch tính), ép đồng bộ Toon + Line Art, đánh dấu sẵn các điểm neo diễn viên (`Stage_Anchors`) và lưu vào `/asset_vault/sets/`.
4. **`04-cinematographer` (Phòng Quay Phim & Diễn Hoạt):**
   - *Kỹ năng:* `skill-camera-grammar.md`, `Camera_Presets.blend`, `stage_compiler.py`.
   - *Nhiệm vụ:* Nạp diễn viên vào phim trường, ghép chuỗi hành động NLA, chạy Rhubarb Lip-Sync, áp ngôn ngữ máy quay điện ảnh (Wide, OTS, Slow Dolly, Handheld, Depth of Field), kiểm duyệt bố cục qua ảnh lưới `contact_sheet.jpg` rồi kích hoạt GPU Render.
5. **`05-motion-editor` (Phòng Đồ Họa Minh Họa & Hậu Kỳ):**
   - *Kỹ năng:* `skill-motion-callouts.md`, Remotion/GSAP templates, FFmpeg compositor.
   - *Nhiệm vụ:* Dựng lớp motion graphics giải thích (biểu đồ, thẻ pop-up, icon nảy lò xo, phụ đề) chuẩn gu *Ifnation / Giáo Sư Bút*, trộn đồng bộ với lớp video từ Blender và file voice/SFX để xuất bản Master `1080p 60fps MP4`.

---

## 4. Workflow Vận Hành Cốt Lõi (Automated Production Pipeline)

```text
[ĐẦU VÀO: Kịch bản + File Voice/Timing của Dự án bất kỳ]
                         │
                         ▼
 1. [01-showrunner] đọc catalog_manifest.json
    ──► Xuất file `episode_shotlist.json` siêu gọn (~1.000 tokens)
                         │
                         ▼
 2. [Engine Local Python — 0 Token]
    - Nạp Set (.blend) + Actor (.blend) + NLA Action + Rhubarb Lip-Sync
    - Render duy nhất 1 ảnh tĩnh cho mỗi cú máy ──► Ghép thành 1 ảnh `contact_sheet.jpg`
                         │
                         ▼
 3. [CỔNG KIỂM DUYỆT NHANH — Self-Review Gate]
    - [04-cinematographer] đọc đúng 1 tấm `contact_sheet.jpg` để kiểm tra góc máy,
      ánh sáng, lỗi che khuất/lẹm khung hình. Tự động sửa JSON nếu phát hiện lỗi.
                         │
                         ▼
 4. [SONG SONG HÓA RENDER — Local GPU + Alpha Overlay]
    ├── Luồng A (Blender GPU EEVEE Next): Render toàn bộ cảnh phim trường & diễn xuất
    └── Luồng B ([05-motion-editor]): Render lớp thẻ minh họa, biểu đồ, phụ đề nền trong suốt
                         │
                         ▼
 5. [FFmpeg Master Compositor — 0 Token]
    ──► Trộn Lớp Phim Trường + Lớp Motion Elements + Voice + SFX/BGM ──► `output_final.mp4`
```

---

## 5. Cấu Trúc Git Repository Chuẩn Tái Sử Dụng (Portable Architecture)
Để kho Git cá nhân gọn nhẹ, dễ đồng bộ và triển khai nhanh trên mọi dự án mới, các file nhị phân nặng (`.blend` tải về, video render) được tách quản lý bằng `.gitignore` / script tải tự động (`bootstrap_studio.py`), giữ cho mã nguồn, Skills, Shaders và Templates luôn sạch sẽ:

```text
/the-studio
├── PROJECT_BLUEPRINT.md          # Bản đặc tả sản phẩm này
├── CLAUDE.md                     # Luật điều phối tổng cho toàn bộ hệ thống Sub-Agents
├── README.md                     # Hướng dẫn 1-lệnh sử dụng cho mọi dự án mới
├── bootstrap_studio.py           # Script 1-lệnh cài đặt dependencies, tải CC0 vault & verify GPU
├── .gitignore                    # Loại trừ file render nặng & cache tạm khỏi Git
├── /.claude/
│   ├── agents/                   # 5 Sub-Agents chuyên biệt (01 đến 05)
│   ├── skills/                   # Kho Skills (Camera, Look-Dev, Pacing, Callouts, Lip-Sync)
│   └── commands/                 # Slash commands tiện ích (/produce-scene, /cast-actor, /build-set)
├── /vault_config/                # Công thức & Shader nhẹ lưu trên Git
│   ├── catalog_manifest.json     # Danh mục tự động toàn bộ Actor, Set, Action, Camera
│   ├── shaders/                  # Script tạo Master Toon Shader & Grease Pencil Line Art
│   ├── presets/                  # Camera rigs, Lighting moods, Character JSON recipes
│   └── motion_templates/         # Bộ template đồ họa Remotion/HTML5+GSAP
├── /engine/                      # Lõi phần mềm chạy Local (0 Token)
│   ├── stage_compiler.py         # Trình biên dịch shotlist.json -> Blender Scene
│   ├── contact_sheet_gen.py      # Xuất lưới ảnh kiểm duyệt bố cục
│   ├── gpu_renderer.py           # Điều phối render Blender EEVEE Next trên GPU
│   ├── lipsync_runner.py         # Wrapper gọi Rhubarb Lip Sync tự động
│   └── master_compositor.py      # Trộn lớp Blender + Motion Overlay + Audio bằng FFmpeg
├── /asset_vault/                 # (Local/Git-LFS) Kho chứa .blend actors, sets, MoCap actions
└── /productions/                 # Thư mục chạy các tập phim / dự án cụ thể
```

---

## 6. Tiêu Chuẩn Bàn Giao Sản Phẩm Cuối Cùng (Definition of Done)
Claude chỉ được coi là hoàn thành nhiệm vụ và bàn giao **THE STUDIO** khi đạt đủ 100% các tiêu chí sau:

1. **Sản phẩm hoàn chỉnh & Chạy độc lập:** Toàn bộ hệ thống 5 Sub-Agents, bộ Skills, Slash Commands và lõi `/engine` hoạt động trơn tru trên máy local, tự động tận dụng GPU để render Blender EEVEE Next.
2. **Kho khởi tạo sẵn sàng sử dụng (Starter Vault):** Tối thiểu sẵn có một bộ diễn viên đa chủng tộc/tuổi tác chuẩn thẩm mỹ phương Tây đã bọc Toon + Line Art, bộ thư viện hành động body language mượt mà, và các bối cảnh mở đa concept (có preset ánh sáng linh hoạt) đã được đăng ký vào `catalog_manifest.json`.
3. **Bản Demo kiểm chứng chất lượng (Verified Showcase):** Xuất thành công ít nhất 01 video showcase hoàn chỉnh (`1080p 60fps MP4`) đi qua đủ toàn bộ quy trình tự động (từ `shotlist.json` $\rightarrow$ `contact_sheet.jpg` $\rightarrow$ GPU Render $\rightarrow$ Motion Graphics Overlay $\rightarrow$ FFmpeg Master) đạt rõ rệt bước nhảy vọt về thẩm mỹ, biểu cảm và tiết kiệm tối đa token.
4. **Đóng gói & Đẩy lên Git cá nhân:** Repository sạch sẽ, có `README.md` rõ ràng, `.gitignore` tối ưu, toàn bộ mã nguồn + cấu hình + Skills đã được commit mạch lạc và đẩy (push) thành công lên remote Git repository cá nhân của chủ dự án để sẵn sàng tái sử dụng cho mọi dự án tương lai.

---
## V2 OVERRIDES (supersede the table in section 2 where they differ)
- Characters: Quaternius stylized CC0 rigs + procedural variant system (skin/hair/eye/palette/accessories) instead of MPFB2; Mixamo drop-in via `engine/ingest_mixamo.py`.
- Sets: real assets only (KayKit, Poly Haven, AmbientCG, HDRI). Primitive-geometry buildings/trees/cars/furniture are forbidden.
- Look: V2 3-band warm toon + weighted ink hull (no ink on eyes/brows/mouth) + HDRI + key/fill/rim + DoF + AO + contact blobs.
- Acting: layered NLA (base + upper body) + blinks + eye tracking + Rhubarb mouth-card visemes + emotes.
- Shotlist contract: `subject_zone` + `ui_safe_zone` per shot; callouts auto-placed; contact sheet shows UI and face boxes.
- Definition of Done additions: `productions/showcase_v2/` A/B benchmark rendered and self-reviewed; no UI over faces.
