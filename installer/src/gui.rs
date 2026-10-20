use alicenation_korean::{EMBEDDED, engine::Engine, package::PackageSet};
use anyhow::Result;
use eframe::egui;
use std::{
    path::PathBuf,
    sync::mpsc::{self, Receiver},
};

enum Message {
    Progress(String),
    Finished(Result<String, String>),
}
#[derive(Clone, Copy)]
enum Action {
    Status,
    Patch,
    Restore,
}

struct App {
    game: String,
    draft: bool,
    package_ok: bool,
    versions: String,
    allow_draft: bool,
    receiver: Option<Receiver<Message>>,
    log: Vec<String>,
    result: String,
    error: bool,
}

impl App {
    fn new(context: &eframe::CreationContext<'_>) -> Self {
        let mut fonts = egui::FontDefinitions::default();
        fonts.font_data.insert(
            "korean".into(),
            egui::FontData::from_static(include_bytes!(
                "../../assets/fonts/HakgyoansimGeurimilgi-Regular.ttf"
            ))
            .into(),
        );
        fonts
            .families
            .get_mut(&egui::FontFamily::Proportional)
            .unwrap()
            .insert(0, "korean".into());
        fonts
            .families
            .get_mut(&egui::FontFamily::Monospace)
            .unwrap()
            .push("korean".into());
        context.egui_ctx.set_fonts(fonts);
        let mut visuals = egui::Visuals::light();
        visuals.panel_fill = egui::Color32::from_rgb(250, 245, 237);
        visuals.override_text_color = Some(egui::Color32::from_rgb(67, 48, 69));
        visuals.selection.bg_fill = egui::Color32::from_rgb(213, 189, 218);
        context.egui_ctx.set_visuals(visuals);
        context.egui_ctx.style_mut(|s| {
            s.spacing.item_spacing = egui::vec2(12.0, 12.0);
            s.text_styles
                .insert(egui::TextStyle::Body, egui::FontId::proportional(20.0));
            s.text_styles
                .insert(egui::TextStyle::Button, egui::FontId::proportional(21.0));
            s.text_styles
                .insert(egui::TextStyle::Heading, egui::FontId::proportional(34.0));
            s.text_styles
                .insert(egui::TextStyle::Small, egui::FontId::proportional(16.0));
        });
        let default = std::env::var_os("ProgramFiles(x86)")
            .map(PathBuf::from)
            .unwrap_or_default()
            .join("Steam/steamapps/common/alicenation");
        let package = PackageSet::read(EMBEDDED);
        Self {
            game: if package.as_ref().is_ok_and(|p| !p.is_draft())
                && default.join("alicenation.exe").is_file()
            {
                default.to_string_lossy().into_owned()
            } else {
                String::new()
            },
            draft: package.as_ref().is_ok_and(|p| p.is_draft()),
            package_ok: package.is_ok(),
            versions: package
                .as_ref()
                .map(|p| {
                    p.versions()
                        .replace("1.0.10-b26075487", "1.0.10 (Steam 빌드 26075487)")
                })
                .unwrap_or_default(),
            allow_draft: false,
            receiver: None,
            log: vec![],
            result: "게임 폴더를 확인하고 원하는 작업을 선택해 주세요.".into(),
            error: false,
        }
    }

    fn start(&mut self, action: Action) {
        let game = PathBuf::from(self.game.trim());
        let allow_draft = self.allow_draft;
        let (tx, rx) = mpsc::channel();
        self.receiver = Some(rx);
        self.log.clear();
        self.result = "작업 중입니다.".into();
        self.error = false;
        std::thread::spawn(move || {
            let result = std::panic::catch_unwind(|| -> Result<String> {
                let engine = Engine::open(&game)?;
                let mut progress = |s: &str| {
                    let _ = tx.send(Message::Progress(s.into()));
                };
                match action {
                    Action::Status => engine.status(),
                    Action::Patch => {
                        engine.install_available(
                            &PackageSet::read(EMBEDDED)?,
                            allow_draft,
                            &mut progress,
                        )?;
                        Ok("한국어 패치를 적용했습니다. 게임을 실행한 뒤 언어 설정에서 한국어를 선택해 주세요.".into())
                    }
                    Action::Restore => {
                        engine.restore(&mut progress)?;
                        Ok("원본 복구를 완료했습니다. 저장 데이터는 그대로 유지됩니다.".into())
                    }
                }
            });
            let result = match result {
                Ok(value) => value.map_err(|e| format!("{e:#}")),
                Err(_) => Err("예기치 않은 오류로 작업이 중단되었습니다. 게임을 닫고 원상 복구를 실행해 주세요.".into()),
            };
            let _ = tx.send(Message::Finished(result));
        });
    }
}

impl eframe::App for App {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        let mut finished = false;
        if let Some(rx) = &self.receiver {
            loop {
                match rx.try_recv() {
                    Ok(Message::Progress(line)) => self.log.push(line),
                    Ok(Message::Finished(result)) => {
                        self.error = result.is_err();
                        self.result = result.unwrap_or_else(|e| e);
                        finished = true;
                        break;
                    }
                    Err(mpsc::TryRecvError::Empty) => break,
                    Err(mpsc::TryRecvError::Disconnected) => {
                        self.error = true;
                        self.result =
                            "작업 연결이 끊겼습니다. 원상 복구로 상태를 확인해 주세요.".into();
                        finished = true;
                        break;
                    }
                }
            }
        }
        if finished {
            self.receiver = None;
        }
        let busy = self.receiver.is_some();
        if busy {
            ctx.request_repaint_after(std::time::Duration::from_millis(100));
            if ctx.input(|i| i.viewport().close_requested()) {
                ctx.send_viewport_cmd(egui::ViewportCommand::CancelClose);
            }
        }
        egui::CentralPanel::default()
            .frame(
                egui::Frame::default()
                    .fill(egui::Color32::from_rgb(250, 245, 237))
                    .inner_margin(28),
            )
            .show(ctx, |ui| {
                ui.heading("앨리스와 피안");
                ui.label(format!("한국어 패치 v1 · 게임 {}", self.versions));
                ui.small("일본어 기준 번역 / 학교안심 그림일기 글꼴");
                if self.draft {
                    ui.colored_label(
                        egui::Color32::from_rgb(155, 83, 20),
                        "제작 중인 시험본입니다. 미번역 리소스가 포함되어 있습니다.",
                    );
                }
                if !self.package_ok {
                    ui.colored_label(
                        egui::Color32::DARK_RED,
                        "패치 데이터가 없는 개발용 빌드입니다. 복구 기능만 사용할 수 있습니다.",
                    );
                }
                ui.separator();
                ui.label("게임 폴더");
                ui.add_enabled_ui(!busy, |ui| {
                    ui.horizontal(|ui| {
                        ui.add(
                            egui::TextEdit::singleline(&mut self.game)
                                .desired_width(520.0)
                                .font(egui::TextStyle::Small),
                        );
                        if ui.button("찾아보기").clicked()
                            && let Some(path) = rfd::FileDialog::new()
                                .set_title("alicenation.exe가 있는 폴더 선택")
                                .pick_folder()
                        {
                            self.game = path.to_string_lossy().into_owned();
                        }
                    });
                    ui.small(
                        "Steam → 게임 속성 → 설치된 파일 → 찾아보기에서 위치를 확인할 수 있습니다.",
                    );
                    if self.draft {
                        ui.checkbox(&mut self.allow_draft, "시험용 게임 사본에 적용합니다");
                    }
                    ui.add_space(6.0);
                    ui.horizontal(|ui| {
                        let can_patch = self.package_ok
                            && (!self.draft || self.allow_draft)
                            && !self.game.trim().is_empty();
                        if ui
                            .add_enabled(
                                can_patch,
                                egui::Button::new("한국어 패치 적용")
                                    .min_size(egui::vec2(210.0, 48.0))
                                    .fill(egui::Color32::from_rgb(222, 203, 228)),
                            )
                            .clicked()
                        {
                            self.start(Action::Patch);
                        }
                        if ui
                            .add_enabled(
                                !self.game.trim().is_empty(),
                                egui::Button::new("원상 복구").min_size(egui::vec2(150.0, 48.0)),
                            )
                            .clicked()
                        {
                            self.start(Action::Restore);
                        }
                        if ui.button("상태 확인").clicked() {
                            self.start(Action::Status);
                        }
                    });
                });
                ui.add_space(6.0);
                if busy {
                    ui.horizontal(|ui| {
                        ui.spinner();
                        ui.label("파일을 처리하고 있습니다. 완료될 때까지 기다려 주세요.");
                    });
                }
                ui.label(egui::RichText::new(&self.result).color(if self.error {
                    egui::Color32::DARK_RED
                } else {
                    egui::Color32::from_rgb(67, 48, 69)
                }));
                egui::ScrollArea::vertical()
                    .max_height(155.0)
                    .stick_to_bottom(true)
                    .show(ui, |ui| {
                        for line in &self.log {
                            ui.small(line);
                        }
                    });
                ui.separator();
                ui.small("원본 백업은 게임 폴더의 .alicenation-korean 폴더에 보관합니다.");
                ui.small("복구가 끝날 때까지 이 백업 폴더를 유지해 주세요.");
            });
    }
}

pub fn run() -> Result<()> {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([790.0, 650.0])
            .with_min_inner_size([750.0, 620.0]),
        ..Default::default()
    };
    eframe::run_native(
        "앨리스와 피안 · 한국어 패치",
        options,
        Box::new(|context| Ok(Box::new(App::new(context)))),
    )
    .map_err(|e| anyhow::anyhow!("인스톨러 화면을 열 수 없습니다: {e}"))
}
