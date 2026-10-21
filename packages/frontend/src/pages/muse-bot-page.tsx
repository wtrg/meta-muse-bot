import * as React from "react";
import { Link } from "react-router";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  Bot,
  Play,
  Square,
  Globe,
  ShieldCheck,
  Check,
  Copy,
  ExternalLink,
  Terminal,
  RefreshCw,
  Sparkles,
  Eye,
  KeyRound,
  Trash2,
  Download,
  FileText,
  FileSpreadsheet,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Activity,
  Info
} from "lucide-react";

type ProxyHealth = {
  ok: boolean;
  is_us?: boolean;
  is_ca?: boolean;
  country_code?: string;
  verdict?: "US_RESIDENTIAL" | "US_DATACENTER" | "CA_ROUTE" | "NON_US" | string;
  verdict_text?: string;
  error?: string;
  data?: {
    query?: string;
    country?: string;
    countryCode?: string;
    city?: string;
    regionName?: string;
    isp?: string;
    org?: string;
    as?: string;
    proxy?: boolean;
    hosting?: boolean;
    ping?: number;
  };
};

type LogEntry = {
  time: string;
  message: string;
  level: "info" | "success" | "warning" | "error";
  progress?: number;
};

type MuseAccount = {
  id: string;
  email: string;
  provider?: string;
  pin?: string;
  otp: string;
  url: string;
  screenshot?: string;
  cookies?: any[];
  createdAt: string;
  status: string;
  invite?: { code?: string; status: string; message?: string };
  requirementsComplete?: boolean;
};

type SessionAccount = {
  stt: number;
  id: string;
  email: string;
  pin: string;
  otpLink: string;
  createdAt?: string;
};

type SessionInfo = {
  sessionId: string;
  sessionTime: string;
  count: number;
  accounts: SessionAccount[];
  hasSession: boolean;
};

type BotRuntimeInfo = {
  ok: boolean;
  build_sha?: string;
  worktree_dirty?: boolean;
  worktree_patch_digest?: string;
  pid?: number;
  python_executable?: string;
  port?: number;
  started_at_utc?: string;
  network_revision?: string;
};

export const MuseBotPage = () => {
  const [count, setCount] = React.useState(1);
  const [isOpeningFreeMuse, setIsOpeningFreeMuse] = React.useState(false);
  const [freeMuseMessage, setFreeMuseMessage] = React.useState("");
  const [provider, setProvider] = React.useState<"clean_tempmail" | "spinupmail">("clean_tempmail");
  const [proxyType, setProxyType] = React.useState<"psiphon" | "vpn" | "custom" | "auto" | "windscribe">("psiphon");
  const [customProxy, setCustomProxy] = React.useState("");
  const [activeProxyInfo, setActiveProxyInfo] = React.useState<{ proxy: string; isp: string; region: string } | null>(null);
  const [inviteCode, setInviteCode] = React.useState("P3FB4N");

  const [isScanningProxy, setIsScanningProxy] = React.useState(false);
  const [psiphonStatus, setPsiphonStatus] = React.useState<{ running: boolean; info?: any } | null>(null);
  const [isTogglingPsiphon, setIsTogglingPsiphon] = React.useState(false);
  const [visible, setVisible] = React.useState(true);
  const [selectedScreenshot, setSelectedScreenshot] = React.useState<string | null>(null);

  const [runtimeInfo, setRuntimeInfo] = React.useState<BotRuntimeInfo | null>(null);
  const [runtimeError, setRuntimeError] = React.useState<boolean>(false);

  const [isRunning, setIsRunning] = React.useState(false);
  const [currentStep, setCurrentStep] = React.useState("Sẵn sàng");
  const [logs, setLogs] = React.useState<LogEntry[]>([]);
  const [accounts, setAccounts] = React.useState<MuseAccount[]>([]);
  const [sessionInfo, setSessionInfo] = React.useState<SessionInfo | null>(null);
  const [copiedKey, setCopiedKey] = React.useState<string | null>(null);
  const [tunnelUrl, setTunnelUrl] = React.useState<string>(
    "https://quad-connected-responsibility-consistency.trycloudflare.com"
  );

  const consoleEndRef = React.useRef<HTMLDivElement>(null);

  const fetchRuntime = React.useCallback(async () => {
    try {
      const res = await fetch("/api/bot/runtime");
      if (res.ok) {
        const data = await res.json();
        if (data.ok) {
          setRuntimeInfo(data);
          setRuntimeError(false);
          return;
        }
      }
      setRuntimeError(true);
    } catch {
      setRuntimeError(true);
    }
  }, []);

  const fetchPsiphonStatus = React.useCallback(async () => {
    try {
      const res = await fetch("/api/bot/psiphon-status");
      if (res.ok) {
        const data = await res.json();
        setPsiphonStatus(data);
      }
    } catch {}
  }, []);

  const handleStartPsiphon = async () => {
    try {
      setIsTogglingPsiphon(true);
      toast.info("Đang khởi động đường hầm Psiphon US ngầm...");
      const res = await fetch("/api/bot/start-psiphon", { method: "POST" });
      const data = await res.json();
      if (res.ok && data.ok) {
        toast.success(`Đã kết nối Psiphon US: ${data.data?.city || "US"} (${data.data?.query || "US IP"})`);
        fetchPsiphonStatus();
        handleCheckProxyHealth();
      } else {
        toast.error(data.error || "Không thể kết nối Psiphon");
      }
    } catch {
      toast.error("Lỗi kết nối");
    } finally {
      setIsTogglingPsiphon(false);
    }
  };

  const handleStopPsiphon = async () => {
    try {
      setIsTogglingPsiphon(true);
      const res = await fetch("/api/bot/stop-psiphon", { method: "POST" });
      if (res.ok) {
        toast.info("Đã dừng đường hầm Psiphon");
        fetchPsiphonStatus();
        setProxyHealth(null);
      }
    } catch {
      toast.error("Lỗi khi dừng Psiphon");
    } finally {
      setIsTogglingPsiphon(false);
    }
  };

  const handleScanProxy = async () => {
    try {
      setIsScanningProxy(true);
      const res = await fetch("/api/bot/auto-proxy", { method: "POST" });
      const data = await res.json();
      if (res.ok && data.ok) {
        setActiveProxyInfo({
          proxy: data.proxy,
          isp: data.isp,
          region: data.region
        });
        setCustomProxy(data.proxy);
        toast.success(`Đã lấy Proxy US dân cư mới: ${data.isp} (${data.region})`);
      } else {
        toast.error(data.error || "Không tìm thấy proxy khả dụng");
      }
    } catch {
      toast.error("Lỗi khi quét proxy");
    } finally {
      setIsScanningProxy(false);
    }
  };

  const [proxyHealth, setProxyHealth] = React.useState<ProxyHealth | null>(null);
  const [isCheckingHealth, setIsCheckingHealth] = React.useState(false);

  const handleCheckProxyHealth = async () => {
    try {
      setIsCheckingHealth(true);
      let proxyValue: string | null = null;
      if (proxyType === "psiphon") {
        proxyValue = null;
      } else if (proxyType === "auto") {
        proxyValue = activeProxyInfo?.proxy || null;
      } else if (proxyType === "custom") {
        proxyValue = customProxy.trim() || null;
      }
      const res = await fetch("/api/bot/check-proxy-health", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ proxy: proxyValue, proxyType })
      });
      const data: ProxyHealth = await res.json();
      setProxyHealth(data);
      if (data.ok) {
        if (data.verdict === "US_RESIDENTIAL") {
          toast.success(data.verdict_text || "Tuyến mạng US Residential chuẩn sạch!");
        } else if (data.verdict === "US_DATACENTER") {
          toast.warning(data.verdict_text || "IP Datacenter có thể bị Meta đưa vào Danh Sách Chờ!");
        } else {
          toast.error(data.verdict_text || "IP không thuộc US! Meta sẽ chặn vùng.");
        }
      } else {
        toast.error(data.error || "Không thể kiểm tra proxy");
      }
      fetchPsiphonStatus();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Lỗi kiểm tra tuyến mạng");
    } finally {
      setIsCheckingHealth(false);
    }
  };

  interface DiagnoseResult {
    ok: boolean;
    provider?: string;
    mode?: string;
    host_probe?: { ip: string; country: string; is_us: boolean; is_ca: boolean; isp: string } | null;
    browser_probe?: { ip: string; country: string; is_us: boolean; is_ca: boolean; isp: string } | null;
    route_match?: boolean;
    muse_rendered_state?: { status: string; message: string; url: string } | null;
    error?: string | null;
    timestamp_utc?: string;
  }

  const [diagnoseResult, setDiagnoseResult] = React.useState<DiagnoseResult | null>(null);
  const [isDiagnosing, setIsDiagnosing] = React.useState(false);

  const handleDiagnoseRoute = async () => {
    try {
      setIsDiagnosing(true);
      toast.info("Đang chẩn đoán tuyến mạng T0 (Host) và T1 (Browser)...");
      let proxyValue: string | null = null;
      if (proxyType === "auto") {
        proxyValue = activeProxyInfo?.proxy || null;
      } else if (proxyType === "custom") {
        proxyValue = customProxy.trim() || null;
      }
      const res = await fetch("/api/bot/diagnose-route", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ proxyType, proxy: proxyValue })
      });
      const data: DiagnoseResult = await res.json();
      if (!res.ok) {
        const detailMsg = (data as unknown as { detail?: string }).detail;
        const errorText = data.error || (detailMsg ? `Lỗi dịch vụ (${res.status}): ${detailMsg}` : `HTTP ${res.status}: ${res.statusText || "Lỗi yêu cầu chẩn đoán"}`);
        setDiagnoseResult({
          ok: false,
          provider: proxyType,
          error: errorText
        });
        toast.error(`Chẩn đoán thất bại: ${errorText}`);
        return;
      }
      setDiagnoseResult(data);
      if (data.ok) {
        toast.success(`Chẩn đoán hoàn tất: Tuyến mạng ${data.browser_probe?.country || "đo được"} khớp chuẩn!`);
      } else {
        toast.warning(data.error || "Chẩn đoán hoàn tất: Tuyến mạng chưa đạt chuẩn hoặc bị từ chối.");
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Lỗi kết nối khi chẩn đoán";
      setDiagnoseResult({
        ok: false,
        provider: proxyType,
        error: errMsg
      });
      toast.error(`Lỗi khi chẩn đoán: ${errMsg}`);
    } finally {
      setIsDiagnosing(false);
    }
  };

  // Poll bot status and accounts
  const fetchStatus = React.useCallback(async () => {
    try {
      const res = await fetch("/api/bot/status");
      if (res.ok) {
        const data = await res.json();
        setIsRunning(data.isRunning);
        setCurrentStep(data.currentStep);
        if (Array.isArray(data.logs)) {
          setLogs(data.logs);
        }
      }
    } catch {
      // Ignore polling errors
    }
  }, []);

  const fetchAccounts = React.useCallback(async () => {
    try {
      const res = await fetch("/api/bot/accounts");
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.accounts)) {
          setAccounts(data.accounts);
        }
      }
    } catch {
      // Ignore polling errors
    }
  }, []);

  const fetchSession = React.useCallback(async () => {
    try {
      const res = await fetch("/api/bot/session-info");
      if (res.ok) {
        const data = await res.json();
        if (data && data.ok) {
          setSessionInfo({
            sessionId: data.sessionId,
            sessionTime: data.sessionTime,
            count: data.count,
            accounts: data.accounts || [],
            hasSession: data.hasSession
          });
        }
      }
    } catch {
      // Ignore polling errors
    }
  }, []);



  React.useEffect(() => {
    fetchRuntime();
    fetchStatus();
    fetchAccounts();
    fetchSession();
    fetchPsiphonStatus();
    fetch("/api/bot/tunnel-info")
      .then(res => res.json())
      .then(data => {
        if (data && data.ok && data.tunnelUrl) {
          setTunnelUrl(data.tunnelUrl);
        }
      })
      .catch(() => {});
    const interval = setInterval(() => {
      fetchRuntime();
      fetchStatus();
      fetchAccounts();
      fetchSession();
      fetchPsiphonStatus();
      }, 2000);
    return () => clearInterval(interval);
  }, [fetchRuntime, fetchStatus, fetchAccounts, fetchSession, fetchPsiphonStatus]);

  // Auto scroll console only inside its container
  React.useEffect(() => {
    if (consoleEndRef.current && consoleEndRef.current.parentElement) {
      consoleEndRef.current.parentElement.scrollTop = consoleEndRef.current.parentElement.scrollHeight;
    }
  }, [logs]);

  const handleStartBot = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    try {
      if (proxyType === "vpn" && proxyHealth && !proxyHealth.is_us && !proxyHealth.is_ca) {
        toast.error(proxyHealth.verdict_text || `Tuyến mạng hiện tại (${proxyHealth.data?.countryCode || "khác"}) không thuộc Hoa Kỳ/Canada.`);
        return;
      }

      let proxyValue: string | null = null;
      if (proxyType === "auto") {
        proxyValue = activeProxyInfo?.proxy || null;
      } else if (proxyType === "custom") {
        proxyValue = customProxy.trim() || null;
      } else if (proxyType === "psiphon") {
        proxyValue = null;
      }

      const res = await fetch("/api/bot/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          count,
          proxy: proxyValue,
          proxyType,
          visible,
          provider,
          domain: "maxxspace.com",
          inviteCode: inviteCode.trim() || undefined
        })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        toast.success("Đã khởi chạy bot tự động tạo tài khoản Muse.ai!");
        fetchStatus();
      } else {
        toast.error(data.detail || data.error || "Không thể khởi chạy bot");
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Lỗi kết nối máy chủ bot");
    }
  };

  const handleOpenFreeMuse = async () => {
    setIsOpeningFreeMuse(true);
    setFreeMuseMessage("Đang kết nối qua tuyến mạng đã chọn và mở Muse...");
    try {
      let proxyValue: string | null = null;
      if (proxyType === "auto") {
        proxyValue = activeProxyInfo?.proxy || null;
      } else if (proxyType === "custom") {
        proxyValue = customProxy.trim() || null;
      }
      const res = await fetch("/api/bot/open-muse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: proxyType, proxy: proxyValue })
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.detail || "Không mở được Muse");
      setFreeMuseMessage(data.message);
      toast.success(data.message);
      fetchPsiphonStatus();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không kết nối được tool";
      setFreeMuseMessage(message);
      toast.error(message);
    } finally {
      setIsOpeningFreeMuse(false);
    }
  };

  const handleOpenSession = async (accountId: string) => {
    try {
      toast.info("Đang khởi động trình duyệt mở phiên đăng nhập...");
      const res = await fetch(`/api/bot/recheck-session/${encodeURIComponent(accountId)}`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        if (data.status === "SUCCESS_CHAT_READY") toast.success(data.message);
        else toast.warning(data.message || "Chưa xác minh được chat");
        fetchAccounts();
      } else {
        toast.error(data.detail || "Không thể mở phiên");
      }
    } catch {
      toast.error("Lỗi khi mở phiên trình duyệt");
    }
  };

  const handleStopBot = async () => {
    try {
      const res = await fetch("/api/bot/stop", { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        toast.warning(data.message || "Đã gửi lệnh dừng");
        fetchStatus();
      }
    } catch {
      toast.error("Không thể kết nối máy chủ bot");
    }
  };

  const handleClearAccounts = async () => {
    if (!confirm("Bạn có chắc chắn muốn xóa toàn bộ lịch sử tài khoản đã tạo?")) return;
    try {
      const res = await fetch("/api/bot/accounts", { method: "DELETE" });
      if (res.ok) {
        setAccounts([]);
        toast.success("Đã xóa lịch sử tài khoản");
      }
    } catch {
      toast.error("Lỗi khi xóa lịch sử");
    }
  };

  const handleCopy = async (text: string, key: string, msg: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      toast.success(msg);
      setTimeout(() => setCopiedKey(null), 2000);
    } catch {
      toast.error("Không thể sao chép");
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground pb-16">
      {/* Top Navbar */}
      <header className="border-b border-border/60 bg-card/60 backdrop-blur sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="size-9 rounded-xl bg-violet-500/15 text-violet-500 flex items-center justify-center font-bold text-lg shadow-sm">
              <Bot className="size-5" />
            </div>
            <div>
              <div className="font-bold tracking-tight text-base flex items-center gap-2">
                <span>Muse.ai Auto Creator</span>
                <Badge variant="outline" className="border-violet-500/40 text-violet-500 bg-violet-500/10 text-[10px] px-1.5 py-0">
                  Bot Tự Động
                </Badge>
                {runtimeInfo ? (
                  <div className="flex items-center gap-1.5 ml-1">
                    <Badge variant="outline" className="border-blue-500/40 text-blue-500 bg-blue-500/10 text-[10px] px-1.5 py-0 font-mono">
                      Rev: {runtimeInfo.build_sha?.slice(0, 7)} | PID: {runtimeInfo.pid}
                    </Badge>
                    {runtimeInfo.worktree_dirty && (
                      <Badge variant="outline" className="border-amber-500/40 text-amber-500 bg-amber-500/10 text-[10px] px-1.5 py-0 font-mono" title={`Patch: ${runtimeInfo.worktree_patch_digest}`}>
                        DIRTY
                      </Badge>
                    )}
                  </div>
                ) : runtimeError ? (
                  <Badge variant="outline" className="border-red-500/40 text-red-500 bg-red-500/10 text-[10px] px-1.5 py-0">
                    Runtime Unreachable
                  </Badge>
                ) : null}
              </div>
              <div className="text-xs text-muted-foreground">
                Tự Reg Mail ➔ Bắt OTP Meta ➔ Điền Ngày Sinh ➔ Đăng Nhập
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              className="text-xs bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20 font-medium"
              onClick={() => window.open("/api/bot/export-session-csv", "_blank")}
              title="Tải file CSV theo số lượng tài khoản của phiên này (không gộp phiên cũ)"
            >
              <Download className="size-3.5 mr-1" />
              <span>Xuất CSV Phiên Này</span>
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="text-xs bg-emerald-600/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 hover:bg-emerald-600/20 font-medium"
              onClick={() => window.open("/api/bot/export-session-excel", "_blank")}
              title="Tải file Excel (.xlsx) theo số lượng tài khoản của phiên này (không gộp phiên cũ)"
            >
              <FileSpreadsheet className="size-3.5 mr-1" />
              <span>Xuất Excel (.xlsx)</span>
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="text-xs text-muted-foreground hover:text-foreground"
              onClick={() => window.open("/api/bot/export-txt", "_blank")}
              title="Tải danh sách tài khoản định dạng TXT"
            >
              <FileText className="size-3.5 mr-1" />
              <span>File TXT</span>
            </Button>
            <Link
              to="/otp"
              className={buttonVariants({ variant: "outline", size: "sm", className: "text-xs" })}
            >
              <KeyRound className="size-3.5 mr-1 text-amber-500" />
              <span>Trang Lấy OTP Khách</span>
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8 space-y-6">
        {/* Public Internet OTP Banner */}
        <div className="bg-gradient-to-r from-violet-500/10 via-emerald-500/10 to-blue-500/10 border border-emerald-500/30 rounded-xl p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="size-9 rounded-lg bg-emerald-500/20 text-emerald-500 flex items-center justify-center shrink-0">
              <Globe className="size-5 animate-pulse" />
            </div>
            <div>
              <div className="font-semibold text-sm flex items-center gap-2">
                <span>Cổng Lấy OTP Công Khai Trực Tuyến (Public Internet)</span>
                <Badge className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[10px] font-mono">
                  ONLINE LIVE
                </Badge>
              </div>
              <div className="text-xs text-muted-foreground mt-0.5">
                Người dùng hoặc khách hàng có thể mở link này trên bất kỳ máy nào để lấy OTP đăng nhập Muse.ai:{" "}
                <a
                  href={`${tunnelUrl}/otp`}
                  target="_blank"
                  rel="noreferrer"
                  className="font-mono text-emerald-600 dark:text-emerald-400 font-semibold underline underline-offset-2 hover:opacity-80"
                >
                  {tunnelUrl}/otp
                </a>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button
              size="sm"
              variant="outline"
              className="text-xs h-8"
              onClick={() => handleCopy(`${tunnelUrl}/otp`, "public-tunnel", "Đã sao chép link trang OTP!")}
            >
              {copiedKey === "public-tunnel" ? (
                <Check className="size-3.5 mr-1 text-emerald-500" />
              ) : (
                <Copy className="size-3.5 mr-1" />
              )}
              <span>Copy Link Trang OTP</span>
            </Button>
            <Button
              size="sm"
              className="text-xs h-8 bg-emerald-600 hover:bg-emerald-700 text-white"
              onClick={() => window.open(`${tunnelUrl}/otp`, "_blank")}
            >
              <ExternalLink className="size-3.5 mr-1" />
              <span>Mở Trang OTP</span>
            </Button>
          </div>
        </div>

        {/* Quick Guide Card */}
        <div className="p-4 rounded-xl border border-violet-500/30 bg-violet-500/5 text-sm space-y-2">
          <div className="font-semibold text-violet-600 dark:text-violet-400 flex items-center gap-2">
            <Sparkles className="size-4" />
            Quy trình tự động 100% dành cho Muse.ai (Meta Account)
          </div>
          <p className="text-muted-foreground leading-relaxed text-xs">
            Bot sẽ tự động: <strong>(1)</strong> Tạo email tiếp nhận mới sạch MX ➔ <strong>(2)</strong> Mở Chrome với IP USA Fake VPN/Proxy ➔ <strong>(3)</strong> Điền email vào Muse.ai ➔ <strong>(4)</strong> Bắt mã OTP gửi từ Meta ➔ <strong>(5)</strong> Tự động nhập OTP & điền ngày sinh hợp lệ ➔ <strong>(6)</strong> Đăng nhập thành công và xuất file txt kèm link OTP trực tuyến.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* LEFT COLUMN: Configuration (5 cols) */}
          <div className="lg:col-span-5 space-y-6">
            <Card className="border-border/80 shadow-md">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Bot className="size-5 text-violet-500" />
                  Cấu Hình Bot Tự Động
                </CardTitle>
                <CardDescription>
                  Thiết lập số lượng và cơ chế Fake VPN/Proxy phù hợp cho Muse.ai
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-5">
                <form onSubmit={handleStartBot} className="space-y-4">
                  {/* Quantity */}
                  <div className="space-y-2">
                    <Label className="text-xs font-semibold">Số lượng tài khoản muốn tạo</Label>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        min={1}
                        max={50}
                        value={count}
                        onChange={e => setCount(Math.max(1, parseInt(e.target.value) || 1))}
                        disabled={isRunning}
                        className="font-mono text-center font-bold text-base"
                      />
                      <div className="flex gap-1.5">
                        {[1, 3, 5, 10].map(n => (
                          <Button
                            key={n}
                            type="button"
                            size="sm"
                            variant={count === n ? "secondary" : "outline"}
                            className="text-xs px-2.5 h-9"
                            disabled={isRunning}
                            onClick={() => setCount(n)}
                          >
                            {n}
                          </Button>
                        ))}
                      </div>
                    </div>
                  </div>



                  {/* Email Provider */}
                  <div className="space-y-2 pt-1 border-t border-border/50">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs font-semibold flex items-center gap-1.5">
                        <Sparkles className="size-3.5 text-violet-500" />
                        Hệ Thống Email Tạo Tài Khoản
                      </Label>
                      <Badge variant="outline" className="text-[10px] bg-emerald-500/10 text-emerald-500 border-emerald-500/30">
                        Nhận mã OTP
                      </Badge>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => setProvider("clean_tempmail")}
                        disabled={isRunning}
                        className={`p-2.5 rounded-lg border text-left transition-all ${
                          provider === "clean_tempmail"
                            ? "border-violet-500 bg-violet-500/10 text-foreground ring-1 ring-violet-500"
                            : "border-border/60 hover:bg-muted/40 text-muted-foreground"
                        }`}
                      >
                        <div className="font-semibold text-xs flex items-center gap-1 text-violet-600 dark:text-violet-400">
                          <Sparkles className="size-3.5 shrink-0" />
                          Clean Domain (fraudfindez.com)
                        </div>
                        <div className="text-[10px] text-muted-foreground mt-0.5 leading-tight">
                          Tên miền sạch chuẩn Meta (loại bỏ hoàn toàn mtempmail)
                        </div>
                      </button>

                      <button
                        type="button"
                        onClick={() => setProvider("spinupmail")}
                        disabled={isRunning}
                        className={`p-2.5 rounded-lg border text-left transition-all ${
                          provider === "spinupmail"
                            ? "border-violet-500 bg-violet-500/10 text-foreground ring-1 ring-violet-500"
                            : "border-border/60 hover:bg-muted/40 text-muted-foreground"
                        }`}
                      >
                        <div className="font-semibold text-xs flex items-center gap-1">
                          <Bot className="size-3.5 text-violet-500 shrink-0" />
                          SpinupMail
                        </div>
                        <div className="text-[10px] text-muted-foreground mt-0.5 leading-tight">
                          Dùng domain tuỳ chỉnh của bạn
                        </div>
                      </button>
                    </div>
                  </div>

                  {/* VPN / Proxy Mechanism */}
                  <div className="space-y-2 pt-1 border-t border-border/50">
                    <Label className="text-xs font-semibold flex items-center gap-1.5">
                      <Globe className="size-3.5 text-primary" />
                      Cơ chế Fake VPN / Vị trí địa lý (Geo-Spoofing)
                    </Label>

                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
                      <button
                        type="button"
                        onClick={() => setProxyType("psiphon")}
                        disabled={isRunning}
                        className={`p-2.5 rounded-lg border text-left transition-all relative ${
                          proxyType === "psiphon"
                            ? "border-violet-500 bg-violet-500/10 text-foreground ring-1 ring-violet-500"
                            : "border-border/60 hover:bg-muted/40 text-muted-foreground"
                        }`}
                      >
                        <span className="absolute -top-1.5 right-1.5 bg-violet-600 text-[9px] text-white font-bold px-1 py-0.2 rounded shadow-xs">
                          Khuyên dùng
                        </span>
                        <div className="font-semibold text-xs flex items-center gap-1 text-violet-600 dark:text-violet-400">
                          <Sparkles className="size-3.5 shrink-0" />
                          Psiphon US
                        </div>
                        <div className="text-[10px] text-muted-foreground mt-0.5 leading-tight">
                          Tự động 100% ngầm
                        </div>
                      </button>

                      <button
                        type="button"
                        onClick={() => setProxyType("windscribe")}
                        disabled={isRunning}
                        className={`p-2.5 rounded-lg border text-left transition-all ${
                          proxyType === "windscribe"
                            ? "border-sky-500 bg-sky-500/10 text-foreground ring-1 ring-sky-500"
                            : "border-border/60 hover:bg-muted/40 text-muted-foreground"
                        }`}
                      >
                        <div className="font-semibold text-xs flex items-center gap-1 text-sky-600 dark:text-sky-400">
                          <ShieldCheck className="size-3.5 shrink-0" />
                          Windscribe CLI
                        </div>
                        <div className="text-[10px] text-muted-foreground mt-0.5 leading-tight">
                          Tài khoản Free máy
                        </div>
                      </button>

                      <button
                        type="button"
                        onClick={() => setProxyType("vpn")}
                        disabled={isRunning}
                        className={`p-2.5 rounded-lg border text-left transition-all ${
                          proxyType === "vpn"
                            ? "border-violet-500 bg-violet-500/10 text-foreground ring-1 ring-violet-500"
                            : "border-border/60 hover:bg-muted/40 text-muted-foreground"
                        }`}
                      >
                        <div className="font-semibold text-xs flex items-center gap-1">
                          <ShieldCheck className="size-3.5 text-violet-500 shrink-0" />
                          VPN Máy (Urban VPN)
                        </div>
                        <div className="text-[10px] text-muted-foreground mt-0.5 leading-tight">
                          Bật Urban VPN chọn mục này
                        </div>
                      </button>

                      <button
                        type="button"
                        onClick={() => setProxyType("custom")}
                        disabled={isRunning}
                        className={`p-2.5 rounded-lg border text-left transition-all ${
                          proxyType === "custom"
                            ? "border-violet-500 bg-violet-500/10 text-foreground ring-1 ring-violet-500"
                            : "border-border/60 hover:bg-muted/40 text-muted-foreground"
                        }`}
                      >
                        <div className="font-semibold text-xs flex items-center gap-1">
                          <Globe className="size-3.5 text-violet-500 shrink-0" />
                          Proxy Riêng
                        </div>
                        <div className="text-[10px] text-muted-foreground mt-0.5 leading-tight">
                          Dán proxy tùy chỉnh
                        </div>
                      </button>

                      <button
                        type="button"
                        onClick={() => setProxyType("auto")}
                        disabled={isRunning}
                        className={`p-2.5 rounded-lg border text-left transition-all ${
                          proxyType === "auto"
                            ? "border-violet-500 bg-violet-500/10 text-foreground ring-1 ring-violet-500"
                            : "border-border/60 hover:bg-muted/40 text-muted-foreground"
                        }`}
                      >
                        <div className="font-semibold text-xs flex items-center gap-1">
                          <RefreshCw className="size-3.5 text-violet-500 shrink-0" />
                          Quét Khác
                        </div>
                        <div className="text-[10px] text-muted-foreground mt-0.5 leading-tight">
                          Proxy dân cư dự phòng
                        </div>
                      </button>
                    </div>

                    {proxyType === "windscribe" && (
                      <div className="p-3 rounded-lg border border-sky-500/30 bg-sky-500/5 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-sky-700 dark:text-sky-300 flex items-center gap-1.5">
                            <span className="size-2 rounded-full bg-emerald-500 animate-pulse" />
                            Windscribe CLI Tự Động Kết Nối (Gói Free)
                          </span>
                        </div>
                        <p className="text-[11px] text-muted-foreground leading-relaxed">
                          Tool sẽ tự động kết nối máy chủ US qua ứng dụng Windscribe trên máy tính của bạn trước khi tạo tài khoản.
                        </p>
                      </div>
                    )}

                    {proxyType === "psiphon" && (
                      <div className="p-3 rounded-lg border border-violet-500/30 bg-violet-500/5 space-y-2.5">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-violet-700 dark:text-violet-300 flex items-center gap-1.5">
                            <span className={`size-2 rounded-full ${psiphonStatus?.running ? "bg-emerald-500 animate-pulse" : "bg-muted-foreground"}`} />
                            Đường Hầm Psiphon US Core (Tích Hợp Sẵn Trong Tool)
                          </span>
                          <div className="flex items-center gap-1.5">
                            {psiphonStatus?.running ? (
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={handleStopPsiphon}
                                disabled={isTogglingPsiphon || isRunning}
                                className="h-6 text-[10px] px-2 text-destructive hover:text-destructive border-destructive/30"
                              >
                                Tắt Hầm
                              </Button>
                            ) : (
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={handleStartPsiphon}
                                disabled={isTogglingPsiphon || isRunning}
                                className="h-6 text-[10px] px-2 bg-violet-500/10 text-violet-600 hover:bg-violet-500/20"
                              >
                                {isTogglingPsiphon ? "Đang bật..." : "Bật Thử Ngay"}
                              </Button>
                            )}
                          </div>
                        </div>

                        <p className="text-[11px] text-muted-foreground leading-relaxed">
                          Tool tự bật Psiphon miễn phí và mở Muse qua đường hầm. Bạn không cần bật VPN bên ngoài. IP Mỹ không bảo đảm Muse cho phép truy cập.
                        </p>

                        <Button
                          type="button"
                          variant="outline"
                          onClick={handleOpenFreeMuse}
                          disabled={isOpeningFreeMuse || isRunning || isTogglingPsiphon}
                          className="w-full"
                        >
                          <ExternalLink className="size-4" />
                          {isOpeningFreeMuse ? "Đang kết nối và mở Muse..." : "Mở Muse qua VPN miễn phí"}
                        </Button>
                        {freeMuseMessage && <p role="status" className="text-xs">{freeMuseMessage}</p>}
                        <p className="text-[11px] text-muted-foreground">
                          Đăng nhập tài khoản đã có trong cửa sổ mới. Nếu Muse báo chặn vùng, kết nối hiện tại chưa đáp ứng điều kiện truy cập.
                        </p>

                        {psiphonStatus?.running && psiphonStatus.info?.data && (
                          <div className="font-mono text-[11px] bg-background/80 p-2 rounded border border-emerald-500/30 flex items-center justify-between">
                            <div className="flex items-center gap-1.5">
                              <CheckCircle2 className="size-3.5 text-emerald-500 shrink-0" />
                              <span className="text-foreground font-semibold">{psiphonStatus.info.data.query}</span>
                              <span className="text-muted-foreground text-[10px]">({psiphonStatus.info.data.city}, US)</span>
                            </div>
                            <span className="text-[10px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold px-1.5 py-0.5 rounded">
                              IP Mỹ/Canada · Chưa kiểm tra chat
                            </span>
                          </div>
                        )}
                      </div>
                    )}

                    {proxyType === "auto" && (
                      <div className="p-2.5 rounded-lg border border-emerald-500/30 bg-emerald-500/5 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-medium text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                            <span className="size-2 rounded-full bg-emerald-500 animate-pulse" />
                            Proxy Dân Cư US Khả Dụng
                          </span>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={handleScanProxy}
                            disabled={isScanningProxy || isRunning}
                            className="h-6 text-[10px] px-2"
                          >
                            <RefreshCw className={`size-3 mr-1 ${isScanningProxy ? "animate-spin" : ""}`} />
                            {isScanningProxy ? "Đang quét..." : "Quét Proxy Khác"}
                          </Button>
                        </div>

                        {activeProxyInfo ? (
                          <div className="font-mono text-xs text-foreground bg-background/80 p-1.5 rounded border border-border/60 flex items-center justify-between">
                            <span className="truncate max-w-[220px]">{activeProxyInfo.proxy}</span>
                            <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
                              {activeProxyInfo.isp}
                            </span>
                          </div>
                        ) : (
                          <div className="text-xs text-muted-foreground italic">
                            Chưa chọn proxy, bấm quét để lấy proxy tự động.
                          </div>
                        )}
                      </div>
                    )}

                    {proxyType === "vpn" && (
                      <div className="p-3 rounded-lg border border-violet-500/30 bg-violet-500/5 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-violet-700 dark:text-violet-300 flex items-center gap-1.5">
                            <ShieldCheck className="size-3.5 text-violet-500 shrink-0" />
                            Đường Tuyến VPN Máy Thật (Urban VPN / Desktop VPN)
                          </span>
                          <span className="text-[10px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold px-2 py-0.5 rounded">
                            Tương thích Urban VPN
                          </span>
                        </div>
                        <p className="text-[11px] text-muted-foreground leading-relaxed">
                          Bật app <strong>Urban VPN</strong> (chọn vị trí <strong>United States</strong>) trên máy tính trước. Tool sẽ sử dụng trực tiếp tuyến mạng IP Dân Cư này kết hợp cùng trình duyệt <strong>Microsoft Edge</strong> (chế độ ẩn danh chống Bot) để tạo tài khoản, giảm thiểu tối đa nguy cơ bị Meta đưa vào Danh Sách Chờ.
                        </p>
                      </div>
                    )}

                    {proxyType === "custom" && (
                      <div className="space-y-1.5 pt-1">
                        <Label className="text-[11px] text-muted-foreground">
                          Nhập Proxy (Ví dụ: <code>http://user:pass@ip:port</code> hoặc <code>socks5://ip:port</code>):
                        </Label>
                        <Input
                          placeholder="http://123.45.67.89:8080"
                          value={customProxy}
                          onChange={e => setCustomProxy(e.target.value)}
                          disabled={isRunning}
                          className="font-mono text-xs"
                        />
                      </div>
                    )}

                    {/* Live IP Health Check Card */}
                    <div className="p-3 rounded-lg border border-border/80 bg-background/60 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold flex items-center gap-1.5">
                          <Activity className="size-3.5 text-violet-500" />
                          Trạng Thái Tuyến Mạng / IP Thoát
                        </span>
                        <div className="flex items-center gap-1.5">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={handleCheckProxyHealth}
                            disabled={isCheckingHealth || isRunning}
                            className="h-7 text-xs px-2 font-medium"
                          >
                            <RefreshCw className={`size-3 mr-1 ${isCheckingHealth ? "animate-spin" : ""}`} />
                            {isCheckingHealth ? "Kiểm tra..." : "Kiểm Tra IP"}
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={handleDiagnoseRoute}
                            disabled={isDiagnosing || isRunning}
                            className="h-7 text-xs px-2 font-medium border-violet-500/40 text-violet-600 dark:text-violet-400 hover:bg-violet-500/10"
                          >
                            <Activity className={`size-3 mr-1 ${isDiagnosing ? "animate-spin" : ""}`} />
                            {isDiagnosing ? "Chẩn đoán..." : "Chẩn Đoán Tuyến Mạng"}
                          </Button>
                        </div>
                      </div>

                      {proxyHealth ? (
                        <div className={`p-2.5 rounded-lg border text-xs space-y-1.5 ${
                          !proxyHealth.ok
                            ? "bg-destructive/10 border-destructive/30 text-destructive dark:text-red-300"
                            : (proxyHealth.verdict === "US_RESIDENTIAL" || proxyHealth.verdict === "US_ROUTE")
                            ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-950 dark:text-emerald-100"
                            : proxyHealth.verdict === "US_DATACENTER"
                            ? "bg-amber-500/10 border-amber-500/30 text-amber-950 dark:text-amber-100"
                            : proxyHealth.verdict === "CA_ROUTE"
                            ? "bg-blue-500/10 border-blue-500/30 text-blue-950 dark:text-blue-100"
                            : "bg-destructive/10 border-destructive/30 text-destructive dark:text-red-300"
                        }`}>
                          <div className="flex items-center gap-2 font-bold">
                            {!proxyHealth.ok ? (
                              <>
                                <XCircle className="size-4 text-destructive shrink-0" />
                                <span>{proxyHealth.error || "Không thể kiểm tra proxy"}</span>
                              </>
                            ) : (
                              <>
                                {(proxyHealth.verdict === "US_RESIDENTIAL" || proxyHealth.verdict === "US_ROUTE") && <CheckCircle2 className="size-4 text-emerald-500 shrink-0" />}
                                {proxyHealth.verdict === "US_DATACENTER" && <AlertTriangle className="size-4 text-amber-500 shrink-0" />}
                                {proxyHealth.verdict === "CA_ROUTE" && <Info className="size-4 text-blue-500 shrink-0" />}
                                {proxyHealth.verdict === "NON_US" && <XCircle className="size-4 text-destructive shrink-0" />}
                                <span>{proxyHealth.verdict_text}</span>
                              </>
                            )}
                          </div>

                          {proxyHealth.ok && proxyHealth.data && (
                            <div className="grid grid-cols-2 gap-x-2 gap-y-1 pt-1 border-t border-border/40 font-mono text-[11px] text-muted-foreground">
                              <div>IP: <span className="text-foreground font-semibold">{proxyHealth.data.query}</span></div>
                              <div>Vùng: <span className="text-foreground">{proxyHealth.data.city}, {proxyHealth.data.countryCode}</span></div>
                              <div className="col-span-2 truncate">ISP: <span className="text-foreground">{proxyHealth.data.isp}</span></div>
                              {proxyHealth.data.ping && <div>Ping: <span className="text-foreground">{proxyHealth.data.ping}s</span></div>}
                              <div>Phân loại: <span className="text-foreground">{proxyHealth.data.hosting ? "Datacenter" : "Residential"}</span></div>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="p-2 rounded bg-muted/40 text-[11px] text-muted-foreground flex items-center justify-between">
                          <span>Chưa kiểm tra. Bấm "Kiểm Tra IP" hoặc "Chẩn Đoán Tuyến Mạng" để xác thực.</span>
                        </div>
                      )}

                      {diagnoseResult && (
                        <div className="p-2.5 rounded-lg border border-border/80 bg-background/80 text-xs space-y-2 mt-2">
                          <div className="flex items-center justify-between font-semibold">
                            <span className="flex items-center gap-1.5 text-foreground">
                              <ShieldCheck className="size-4 text-violet-500" />
                              Kết Quả Chẩn Đoán Tuyến Mạng (T0 / T1)
                            </span>
                            <Badge variant={diagnoseResult.ok ? "default" : "destructive"} className="text-[10px]">
                              {diagnoseResult.ok ? "KHỚP CHUẨN" : "CẦN LƯU Ý"}
                            </Badge>
                          </div>
                          
                          {diagnoseResult.error && (
                            <div className="p-2 rounded bg-destructive/10 border border-destructive/30 text-destructive text-[11px] font-semibold flex items-start gap-1.5">
                              <XCircle className="size-4 shrink-0 mt-0.5" />
                              <span>{diagnoseResult.error}</span>
                            </div>
                          )}

                          <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                            <div className="p-2 rounded bg-muted/30 border border-border/40">
                              <div className="font-sans font-semibold text-muted-foreground mb-1">T0 (Host Exit)</div>
                              <div>IP: <span className="text-foreground">{diagnoseResult.host_probe?.ip || "N/A"}</span></div>
                              <div>Quốc gia: <span className="text-foreground">{diagnoseResult.host_probe?.country || "N/A"}</span></div>
                              <div className="truncate">ISP: <span className="text-foreground">{diagnoseResult.host_probe?.isp || "N/A"}</span></div>
                            </div>
                            <div className="p-2 rounded bg-muted/30 border border-border/40">
                              <div className="font-sans font-semibold text-muted-foreground mb-1">T1 (Browser Exit)</div>
                              <div>IP: <span className="text-foreground">{diagnoseResult.browser_probe?.ip || "N/A"}</span></div>
                              <div>Quốc gia: <span className="text-foreground">{diagnoseResult.browser_probe?.country || "N/A"}</span></div>
                              <div className="truncate">ISP: <span className="text-foreground">{diagnoseResult.browser_probe?.isp || "N/A"}</span></div>
                            </div>
                          </div>

                          {diagnoseResult.muse_rendered_state && (
                            <div className="p-2 rounded bg-muted/20 border border-border/40 text-[11px]">
                              <span className="font-semibold text-muted-foreground">Quan sát Muse Landing (Chưa đăng ký): </span>
                              <span className="font-mono text-foreground font-semibold">{diagnoseResult.muse_rendered_state.status}</span>
                              <p className="text-[10px] text-muted-foreground mt-0.5">{diagnoseResult.muse_rendered_state.message}</p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="text-[11px] text-muted-foreground bg-muted/40 p-2.5 rounded-md leading-relaxed">
                      💡 <strong>Kiểm tra quyền truy cập:</strong> Kết nối IP Mỹ/Canada và nhận OTP chưa đồng nghĩa với việc vào được chat. Tool chỉ báo thành công sau khi thấy ô chat hoạt động.
                    </div>
                  </div>

                  {/* Meta Muse Invite Code Card */}
                  <div className="space-y-2 pt-2 border-t border-border/50">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs font-semibold flex items-center gap-1.5">
                        <Sparkles className="size-3.5 text-violet-500" />
                        Mã Mời Meta Muse (Invite Code / Link Mời)
                      </Label>
                      <Badge variant="outline" className="text-[10px] bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/30">
                        Mã giới thiệu (tùy chọn)
                      </Badge>
                    </div>

                    <div className="flex gap-2">
                      <Input
                        placeholder="Nhập mã 6 ký tự hoặc link https://muse.ai/invite/..."
                        value={inviteCode}
                        onChange={e => setInviteCode(e.target.value)}
                        disabled={isRunning}
                        className="font-mono font-medium text-sm tracking-wider"
                      />
                      {inviteCode && (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => setInviteCode("")}
                          disabled={isRunning}
                          className="text-xs h-9 shrink-0"
                          title="Xóa mã mời"
                        >
                          Xóa
                        </Button>
                      )}
                    </div>

                    <p className="text-[11px] text-muted-foreground leading-relaxed">
                      🎯 <strong>Quy đổi mã:</strong> Mã mời (nếu có) chỉ được gửi quy đổi trong Cài đặt sau khi tài khoản vào màn hình Chat thành công. Để trống nếu không dùng mã.
                    </p>
                  </div>




                  {/* Browser Visibility */}
                  <div className="pt-2 border-t border-border/50 flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label className="text-xs font-semibold flex items-center gap-1.5">
                        <Eye className="size-3.5 text-primary" />
                        Hiển thị cửa sổ Chrome khi chạy
                      </Label>
                      <p className="text-[11px] text-muted-foreground">
                        Mở cửa sổ để bạn theo dõi trực tiếp từng bước bot điền
                      </p>
                    </div>
                    <input
                      type="checkbox"
                      checked={visible}
                      onChange={e => setVisible(e.target.checked)}
                      disabled={isRunning}
                      className="size-4 rounded accent-primary cursor-pointer"
                    />
                  </div>

                  {/* Actions */}
                  <div className="pt-3">
                    {!isRunning ? (
                      <Button
                        type="submit"
                        className="w-full bg-violet-600 hover:bg-violet-700 text-white font-bold h-11 shadow-md shadow-violet-500/20"
                      >
                        <Play className="size-4 mr-2 fill-current" />
                        BẮT ĐẦU TỰ ĐỘNG TẠO TÀI KHOẢN
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        variant="destructive"
                        onClick={handleStopBot}
                        className="w-full h-11 font-bold shadow-md shadow-red-500/20 animate-pulse"
                      >
                        <Square className="size-4 mr-2 fill-current" />
                        DỪNG QUY TRÌNH BOT
                      </Button>
                    )}
                  </div>
                </form>
              </CardContent>
            </Card>

            {/* Current State Indicator */}
            <Card className="border-border/80 shadow-md">
              <CardContent className="pt-5 pb-5">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Trạng thái hiện tại
                  </div>
                  <Badge
                    variant="outline"
                    className={
                      isRunning
                        ? "border-emerald-500/40 text-emerald-500 bg-emerald-500/10 font-bold animate-pulse"
                        : "border-border text-muted-foreground"
                    }
                  >
                    {isRunning ? "● Đang hoạt động" : "○ Đang chờ lệnh"}
                  </Badge>
                </div>
                <div className="font-medium text-sm text-foreground bg-muted/40 p-3 rounded-lg border border-border/50 flex items-center gap-2">
                  {isRunning && <RefreshCw className="size-4 text-emerald-500 animate-spin shrink-0" />}
                  <span>{currentStep}</span>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* RIGHT COLUMN: Live Console & Accounts (7 cols) */}
          <div className="lg:col-span-7 space-y-6">
            {/* Live Terminal Console */}
            <Card className="border-border/80 shadow-md flex flex-col h-[380px]">
              <CardHeader className="py-3 px-4 border-b border-border/60 bg-muted/20 flex flex-row items-center justify-between">
                <div className="flex items-center gap-2 font-mono text-xs font-semibold">
                  <Terminal className="size-4 text-emerald-500" />
                  <span>Nhật Ký Trực Tiếp (Live Console)</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-muted-foreground">
                    {logs.length} dòng log
                  </span>
                </div>
              </CardHeader>

              <CardContent className="p-3 flex-1 overflow-y-auto bg-black/95 text-zinc-100 font-mono text-xs space-y-1.5 select-text rounded-b-lg">
                {logs.length === 0 ? (
                  <div className="text-zinc-500 italic p-4 text-center">
                    Chưa có nhật ký nào. Nhấn "Bắt đầu tạo tài khoản" để xem tiến trình.
                  </div>
                ) : (
                  logs.map((log, idx) => (
                    <div key={idx} className="flex items-start gap-2 leading-relaxed">
                      <span className="text-zinc-500 shrink-0">[{log.time}]</span>
                      <span
                        className={
                          log.level === "success"
                            ? "text-emerald-400 font-bold"
                            : log.level === "error"
                            ? "text-rose-400 font-bold"
                            : log.level === "warning"
                            ? "text-amber-400 font-semibold"
                            : "text-zinc-300"
                        }
                      >
                        {log.message}
                      </span>
                    </div>
                  ))
                )}
                <div ref={consoleEndRef} />
              </CardContent>
            </Card>

            {/* CURRENT SESSION CARD: CSV & EXCEL EXPORT PER BATCH */}
            <Card className="border-emerald-500/40 bg-card shadow-md">
              <CardHeader className="py-3.5 px-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/60 bg-emerald-500/5">
                <div>
                  <div className="flex items-center gap-2">
                    <FileSpreadsheet className="size-4 text-emerald-500" />
                    <CardTitle className="text-base text-foreground flex items-center gap-2">
                      <span>Xuất File Theo Phiên Vừa Tạo ({sessionInfo?.count ?? 0} tài khoản)</span>
                    </CardTitle>
                    <Badge className="bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[10px]">
                      Không Gộp Phiên Cũ
                    </Badge>
                  </div>
                  <CardDescription className="text-xs mt-1">
                    Chia đúng 4 cột: <strong>Cột 1: STT | Cột 2: Email | Cột 3: Mã PIN | Cột 4: Trang Web Lấy OTP</strong>
                  </CardDescription>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => window.open("/api/bot/export-session-csv", "_blank")}
                    className="text-xs h-8 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20 font-semibold"
                  >
                    <Download className="size-3.5 mr-1" />
                    Tải File CSV (.csv)
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => window.open("/api/bot/export-session-excel", "_blank")}
                    className="text-xs h-8 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold shadow-sm"
                  >
                    <FileSpreadsheet className="size-3.5 mr-1" />
                    Tải Excel (.xlsx)
                  </Button>
                </div>
              </CardHeader>

              <CardContent className="p-0">
                {(!sessionInfo || sessionInfo.accounts.length === 0) ? (
                  <div className="p-6 text-center text-muted-foreground text-xs italic">
                    Chưa có tài khoản nào được tạo ở phiên này. Nhấn "Bắt Đầu Tự Động Tạo Tài Khoản" để khởi chạy.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-muted/40 text-muted-foreground uppercase text-[10px] tracking-wider border-b border-border/60">
                        <tr>
                          <th className="py-2.5 px-3 w-14 text-center">STT</th>
                          <th className="py-2.5 px-3">Email</th>
                          <th className="py-2.5 px-3 w-28 text-center">Mã PIN</th>
                          <th className="py-2.5 px-3">Trang Web Lấy OTP Đăng Nhập</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {sessionInfo.accounts.map((acc) => (
                          <tr key={acc.id || acc.stt} className="hover:bg-muted/30 transition-colors">
                            <td className="py-2.5 px-3 text-center font-bold text-muted-foreground">{acc.stt}</td>
                            <td className="py-2.5 px-3 font-mono font-medium text-foreground">{acc.email}</td>
                            <td className="py-2.5 px-3 text-center">
                              <span className="font-mono bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 px-2 py-0.5 rounded font-bold">
                                {acc.pin}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 font-mono text-[11px]">
                              <div className="flex items-center gap-2">
                                <a
                                  href={acc.otpLink}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-emerald-600 dark:text-emerald-400 underline underline-offset-2 hover:opacity-80 truncate max-w-xs md:max-w-md block"
                                >
                                  {acc.otpLink}
                                </a>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-6 px-1.5 text-[11px] text-muted-foreground hover:text-foreground shrink-0"
                                  onClick={() => handleCopy(acc.otpLink, `sess-link-${acc.stt}`, "Đã copy link OTP!")}
                                >
                                  {copiedKey === `sess-link-${acc.stt}` ? (
                                    <Check className="size-3 text-emerald-500" />
                                  ) : (
                                    <Copy className="size-3" />
                                  )}
                                </Button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Results Table */}
            <Card className="border-border/80 shadow-md">
              <CardHeader className="py-3.5 px-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/60">
                <div>
                  <CardTitle className="text-base flex items-center gap-2">
                    <ShieldCheck className="size-4 text-emerald-500" />
                    Lịch Sử Tài Khoản Muse.ai ({accounts.length})
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Tài khoản đã xác thực OTP xong, có mã PIN và đường link lấy OTP trực tuyến
                  </CardDescription>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => window.open("/api/bot/export-txt", "_blank")}
                    className="text-xs h-8 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20 font-medium"
                  >
                    <Download className="size-3.5 mr-1" />
                    Tải File TXT (.txt)
                  </Button>
                  {accounts.length > 0 && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={handleClearAccounts}
                      className="text-xs h-8 text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="size-3 mr-1" />
                      Xóa lịch sử
                    </Button>
                  )}
                </div>
              </CardHeader>

              <CardContent className="p-0">
                {accounts.length === 0 ? (
                  <div className="p-8 text-center text-muted-foreground text-xs italic">
                    Chưa có tài khoản nào được tạo xong.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-muted/40 text-muted-foreground uppercase text-[10px] tracking-wider border-b border-border/60">
                        <tr>
                          <th className="py-2.5 px-3">#</th>
                          <th className="py-2.5 px-3">Email Muse.ai</th>
                          <th className="py-2.5 px-3">Mã PIN/OTP</th>
                          <th className="py-2.5 px-3">Link Nhận OTP Cho Khách</th>
                          <th className="py-2.5 px-3">Trạng Thái</th>
                          <th className="py-2.5 px-3">Thời Gian</th>
                          <th className="py-2.5 px-3 text-right">Thao Tác</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {accounts.map((acc, idx) => {
                          const pin = acc.pin || "";
                          const clientOtpUrl = `${tunnelUrl}/otp?email=${encodeURIComponent(acc.email)}`;
                          return (
                            <tr key={acc.id} className="hover:bg-muted/30 transition-colors">
                              <td className="py-2.5 px-3 text-muted-foreground">{idx + 1}</td>
                              <td className="py-2.5 px-3 font-mono font-medium">{acc.email}</td>
                              <td className="py-2.5 px-3">
                                <span className="font-mono bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 px-2 py-0.5 rounded font-bold">
                                  {pin}
                                </span>
                              </td>
                              <td className="py-2.5 px-3">
                                <div className="flex items-center gap-1.5">
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-6 px-2 text-[11px] text-emerald-600 dark:text-emerald-400 border-emerald-500/30 bg-emerald-500/5 hover:bg-emerald-500/15"
                                    onClick={() => handleCopy(clientOtpUrl, `link-${idx}`, "Đã chép link lấy OTP cho khách!")}
                                  >
                                    {copiedKey === `link-${idx}` ? (
                                      <Check className="size-3 mr-1 text-emerald-500" />
                                    ) : (
                                      <Copy className="size-3 mr-1" />
                                    )}
                                    <span>Copy Link OTP</span>
                                  </Button>
                                  <a
                                    href={clientOtpUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="text-muted-foreground hover:text-foreground p-1"
                                    title="Mở kiểm tra link OTP"
                                  >
                                    <ExternalLink className="size-3" />
                                  </a>
                                </div>
                              </td>
                              <td className="py-2.5 px-3">
                                {acc.status === "SUCCESS_CHAT_READY" ? (
                                  <Badge variant="outline" className="border-emerald-500/40 text-emerald-500 bg-emerald-500/10 text-[10px] font-bold">
                                    CHAT SẴN SÀNG
                                  </Badge>
                                ) : (
                                  <Badge variant="outline" className="border-amber-500/40 text-amber-500 bg-amber-500/10 text-[10px] font-medium">
                                    {({ WAITLISTED_GEOGATED: "CHẶN QUỐC GIA/KHU VỰC", WAITLISTED: "DANH SÁCH CHỜ", LOGIN_REQUIRED: "CHƯA ĐĂNG NHẬP XONG", ACCESS_PENDING: "CHƯA CÓ QUYỀN CHAT", ACCESS_UNVERIFIED: "CHƯA XÁC MINH CHAT" } as Record<string, string>)[acc.status] || "CHƯA XÁC MINH CHAT"}
                                  </Badge>
                                )}
                              </td>
                              <td className="py-2.5 px-3 text-muted-foreground whitespace-nowrap">
                                {acc.invite && <div className="text-[10px] mb-1">Mã {acc.invite.code}: {acc.invite.status === "REDEEMED" ? "ĐÃ ĐỔI THÀNH CÔNG" : "CHƯA XÁC NHẬN ĐỔI MÃ"}</div>}
                                {acc.createdAt}
                              </td>
                              <td className="py-2.5 px-3 text-right space-x-1.5 whitespace-nowrap">
                                <Button
                                  size="sm"
                                  variant="default"
                                  className="h-7 px-2 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                                  onClick={() => handleOpenSession(acc.id)}
                                >
                                  <ExternalLink className="size-3 mr-1" />
                                  Mở & kiểm tra
                                </Button>

                                {acc.cookies && acc.cookies.length > 0 && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 px-2 text-xs"
                                    onClick={() =>
                                      handleCopy(
                                        JSON.stringify(acc.cookies),
                                        `cookie-${idx}`,
                                        "Đã sao chép Session Cookies!"
                                      )
                                    }
                                  >
                                    {copiedKey === `cookie-${idx}` ? (
                                      <Check className="size-3 text-emerald-500" />
                                    ) : (
                                      <KeyRound className="size-3" />
                                    )}
                                    <span className="ml-1">Cookies</span>
                                  </Button>
                                )}

                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-7 px-2 text-xs"
                                  onClick={() => handleCopy(acc.email, `mail-${idx}`, "Đã chép Email")}
                                >
                                  {copiedKey === `mail-${idx}` ? (
                                    <Check className="size-3 text-emerald-500" />
                                  ) : (
                                    <Copy className="size-3" />
                                  )}
                                  <span className="ml-1">Mail</span>
                                </Button>

                                {acc.screenshot && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 px-2 text-xs"
                                    onClick={() => setSelectedScreenshot(acc.screenshot || null)}
                                  >
                                    <Eye className="size-3 mr-1" />
                                    Ảnh
                                  </Button>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>

      {/* Screenshot Preview Modal */}
      {selectedScreenshot && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4 backdrop-blur-sm"
          onClick={() => setSelectedScreenshot(null)}
        >
          <div
            className="bg-card border border-border rounded-xl max-w-4xl w-full p-4 space-y-3 max-h-[90vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <div className="font-semibold text-sm flex items-center gap-2">
                <ShieldCheck className="size-4 text-emerald-500" />
                <span>Ảnh chụp màn hình thực tế xác thực Muse.ai</span>
              </div>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 px-2 text-xs"
                onClick={() => setSelectedScreenshot(null)}
              >
                Đóng
              </Button>
            </div>
            <div className="rounded-lg overflow-hidden border border-border/60 bg-muted/20">
              <img
                src={`/api/bot/screenshot/${selectedScreenshot}`}
                alt="Muse Screen"
                className="w-full h-auto object-contain"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
