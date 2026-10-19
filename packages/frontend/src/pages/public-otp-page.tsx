import * as React from "react";
import { useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "sonner";

type OtpResult = {
  ok: boolean;
  hasEmails: boolean;
  address?: string;
  message?: string;
  error?: string;
  latest?: {
    id: string;
    from: string;
    sender: string | null;
    subject: string | null;
    receivedAt: string | null;
    otp: string | null;
    magicLink: string | null;
    bodyText: string | null;
    bodyHtml: string | null;
  };
  totalEmails?: number;
  isLocalDevDomain?: boolean;
};

export const PublicOtpPage = () => {
  const [searchParams] = useSearchParams();
  const urlEmail = searchParams.get("email") || searchParams.get("mail") || "";
  const urlPin = searchParams.get("pin") || "";

  const [email, setEmail] = React.useState(urlEmail);
  const [pin, setPin] = React.useState(urlPin);
  const [loading, setLoading] = React.useState(false);
  const [autoRefresh, setAutoRefresh] = React.useState(Boolean(urlEmail && urlPin));
  const [data, setData] = React.useState<OtpResult | null>(null);
  const [copied, setCopied] = React.useState(false);
  const [copiedAccount, setCopiedAccount] = React.useState(false);
  const [showBody, setShowBody] = React.useState(false);

  React.useEffect(() => {
    if (urlEmail) setEmail(urlEmail);
    if (urlPin) setPin(urlPin);
    if (urlEmail && urlPin) {
      setAutoRefresh(true);
    }
  }, [urlEmail, urlPin]);

  const fetchOtp = React.useCallback(
    async (showLoadingSpinner = true, overrideEmail?: string, overridePin?: string) => {
      const targetMail = (overrideEmail !== undefined ? overrideEmail : email).trim().toLowerCase();
      const targetPin = (overridePin !== undefined ? overridePin : pin).trim();

      if (!targetMail) {
        toast.error("Vui lòng nhập địa chỉ email");
        return;
      }
      if (!targetPin) {
        toast.error("Vui lòng nhập mã PIN bảo mật");
        return;
      }

      if (showLoadingSpinner) {
        setLoading(true);
      }

      try {
        const response = await fetch(
          `/api/public/otp?email=${encodeURIComponent(targetMail)}&pin=${encodeURIComponent(targetPin)}`
        );
        const result = (await response.json()) as OtpResult;

        if (!response.ok || !result.ok) {
          setData(null);
          toast.error(result.error || "Không thể lấy thông tin OTP");
        } else {
          setData(result);
        }
      } catch {
        toast.error("Lỗi kết nối máy chủ");
      } finally {
        if (showLoadingSpinner) {
          setLoading(false);
        }
      }
    },
    [email, pin]
  );

  // Auto-fetch on mount or whenever URL params change
  React.useEffect(() => {
    if (urlEmail && urlPin) {
      void fetchOtp(true, urlEmail, urlPin);
    }
  }, [urlEmail, urlPin, fetchOtp]);

  // Auto-refresh polling every 3 seconds if enabled
  React.useEffect(() => {
    if (!autoRefresh || !email.trim() || !pin.trim()) return;

    const interval = setInterval(() => {
      void fetchOtp(false);
    }, 3000);

    return () => clearInterval(interval);
  }, [autoRefresh, email, pin, fetchOtp]);

  const handleCopyOtp = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      toast.success("Đã sao chép mã OTP!");
      setTimeout(() => setCopied(false), 2500);
    } catch {
      toast.error("Không thể tự động sao chép, vui lòng bôi đen để copy");
    }
  };

  const handleCopyAccountFormat = async () => {
    const formatted = `${email.trim()} | PIN: ${pin.trim()}`;
    try {
      await navigator.clipboard.writeText(formatted);
      setCopiedAccount(true);
      toast.success("Đã sao chép định dạng tài khoản!");
      setTimeout(() => setCopiedAccount(false), 2500);
    } catch {
      toast.error("Không thể copy");
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center p-4 sm:p-6">
      <div className="w-full max-w-xl space-y-6">
        {/* Brand header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-semibold tracking-wide">
            <span>⚡ HỆ THỐNG LẤY OTP TỰ ĐỘNG</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            Lấy Mã OTP Muse.ai
          </h1>
          <p className="text-sm text-muted-foreground">
            Nhập email và mã PIN để lấy mã xác thực hoặc link đăng nhập mới nhất.
          </p>
        </div>

        {/* Input Card */}
        <Card className="border border-border/80 shadow-md">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-medium">Thông tin hòm thư</CardTitle>
            <CardDescription className="text-xs">
              Mã PIN giúp bảo vệ hòm thư, chỉ người có mã mới xem được OTP của tài khoản này.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">
                Địa chỉ Email
              </label>
              <Input
                type="email"
                placeholder="ví dụ: muse_user01@domain.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="font-mono text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">
                Mã PIN bảo mật
              </label>
              <Input
                type="text"
                placeholder="ví dụ: 827192"
                value={pin}
                onChange={e => setPin(e.target.value)}
                className="font-mono text-sm tracking-wider"
              />
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
              <label className="flex items-center gap-2 cursor-pointer text-xs text-muted-foreground select-none">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={e => setAutoRefresh(e.target.checked)}
                  className="rounded border-border text-primary size-4"
                />
                <span>Tự động cập nhật mỗi 3 giây</span>
                {autoRefresh && (
                  <span className="flex h-2 w-2 relative">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                )}
              </label>

              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  onClick={() => void fetchOtp(true)}
                  disabled={loading}
                  className="font-medium text-xs sm:text-sm px-4"
                >
                  {loading ? (
                    <>
                      <Spinner className="size-4 mr-2" />
                      <span>Đang kiểm tra...</span>
                    </>
                  ) : (
                    <span>Lấy mã OTP</span>
                  )}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Results display */}
        {data && (
          <div className="space-y-4 animate-in fade-in duration-300">
            {!data.hasEmails ? (
              <Card className="border border-dashed border-amber-500/40 bg-amber-500/5">
                <CardContent className="pt-6 text-center space-y-2">
                  <div className="text-2xl">⏳</div>
                  <h3 className="font-semibold text-sm text-foreground">
                    Đang chờ Muse.ai gửi mã xác thực...
                  </h3>
                  <p className="text-xs text-muted-foreground max-w-md mx-auto">
                    {data.message ||
                      "Chưa có thư mới nào gửi đến. Vui lòng bấm gửi mã OTP trên trang Muse.ai, sau đó quay lại trang này (hệ thống sẽ tự nhận mã)."}
                  </p>
                  {data.isLocalDevDomain && (
                    <div className="mt-4 p-3 rounded-lg bg-amber-500/15 border border-amber-500/30 text-xs text-amber-700 dark:text-amber-300 text-left max-w-lg mx-auto space-y-1.5">
                      <div className="font-semibold flex items-center gap-1.5">
                        ⚠️ Nguyên nhân chưa nhận được mã:
                      </div>
                      <div>
                        Email này mang đuôi <code>@spinupmail.dev</code> (tên miền thử nghiệm nội bộ local). Máy chủ Muse.ai trên internet không thể gửi thư tới máy tính của bạn qua tên miền này.
                      </div>
                      <div className="pt-1 font-medium">
                        👉 <strong>Giải pháp:</strong> Hãy sang <a href="/bulk" className="underline font-bold text-primary">Trang Tạo Mail Hàng Loạt (/bulk)</a> và chọn đuôi <strong>@maxxspace.com</strong> (Email THẬT nhận được từ internet 100%) để đăng ký tài khoản Muse.ai!
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            ) : (
              <Card className="border-2 border-primary/40 bg-card shadow-lg">
                <CardHeader className="pb-3 border-b border-border/40">
                  <div className="flex items-center justify-between">
                    <Badge variant="outline" className="text-xs font-mono text-emerald-600 dark:text-emerald-400 border-emerald-500/40 bg-emerald-500/10">
                      ✓ Đã nhận thư mới
                    </Badge>
                    <span className="text-[11px] text-muted-foreground">
                      {data.latest?.receivedAt
                        ? new Date(data.latest.receivedAt).toLocaleTimeString("vi-VN")
                        : ""}
                    </span>
                  </div>
                  <CardTitle className="text-base font-bold text-foreground pt-1">
                    {data.latest?.subject || "(Không có tiêu đề)"}
                  </CardTitle>
                  <CardDescription className="text-xs truncate">
                    Người gửi: {data.latest?.from}
                  </CardDescription>
                </CardHeader>

                <CardContent className="space-y-5 pt-4">
                  {/* Highlighted OTP Code */}
                  {data.latest?.otp ? (
                    <div className="p-4 rounded-xl bg-primary/10 border border-primary/30 text-center space-y-3">
                      <div className="text-xs uppercase tracking-widest font-semibold text-primary">
                        Mã Xác Thực OTP Của Bạn
                      </div>
                      <div className="text-4xl sm:text-5xl font-extrabold tracking-widest font-mono text-foreground select-all py-1">
                        {data.latest.otp}
                      </div>
                      <Button
                        type="button"
                        size="lg"
                        className="w-full sm:w-auto font-bold px-8 shadow-sm"
                        onClick={() => handleCopyOtp(data.latest!.otp!)}
                      >
                        {copied ? "✓ ĐÃ SAO CHÉP MÃ!" : "Sao chép mã OTP"}
                      </Button>
                    </div>
                  ) : (
                    <div className="p-3 rounded-lg bg-muted text-center text-xs text-muted-foreground">
                      Không tìm thấy mã số ngắn trong email. Vui lòng xem link hoặc nội dung bên dưới.
                    </div>
                  )}

                  {/* Magic Link / Direct Confirmation Link */}
                  {data.latest?.magicLink && (
                    <div className="p-3.5 rounded-lg border border-blue-500/30 bg-blue-500/10 space-y-2 text-center">
                      <p className="text-xs font-medium text-blue-600 dark:text-blue-400">
                        🔗 Phát hiện đường link xác thực Muse.ai:
                      </p>
                      <a
                        href={data.latest.magicLink}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-block w-full sm:w-auto px-4 py-2 rounded-md bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors"
                      >
                        Mở link kích hoạt tài khoản Muse.ai ↗
                      </a>
                    </div>
                  )}

                  {/* Full email content toggle */}
                  <div className="pt-2 border-t border-border/40">
                    <button
                      type="button"
                      onClick={() => setShowBody(prev => !prev)}
                      className="text-xs text-muted-foreground hover:text-foreground font-medium underline flex items-center gap-1"
                    >
                      {showBody ? "Thu gọn nội dung email ▲" : "Xem toàn bộ nội dung email nhận được ▼"}
                    </button>

                    {showBody && (
                      <div className="mt-3 p-3 rounded-md bg-muted/50 border border-border/60 text-xs text-foreground font-mono whitespace-pre-wrap max-h-72 overflow-y-auto">
                        {data.latest?.bodyText || (
                          <div
                            dangerouslySetInnerHTML={{
                              __html: data.latest?.bodyHtml || "(Không có nội dung)",
                            }}
                          />
                        )}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* Quick link sharing tip */}
        <div className="p-3.5 rounded-lg border border-border/70 bg-card/60 text-xs text-muted-foreground space-y-2">
          <p className="font-semibold text-foreground">💡 Dành cho người bán / chia sẻ tài khoản:</p>
          <p>
            Bạn có thể gửi cho khách link tự động dạng:
            <br />
            <code className="text-primary font-mono text-[11px] block mt-1 p-1 bg-muted rounded truncate">
              {window.location.origin}/otp?mail={email || "acc01@domain.com"}&pin={pin || "827192"}
            </code>
          </p>
          <div className="flex gap-2 pt-1">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="text-xs h-7"
              onClick={handleCopyAccountFormat}
            >
              {copiedAccount ? "✓ Đã chép" : "Copy Email | PIN"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
