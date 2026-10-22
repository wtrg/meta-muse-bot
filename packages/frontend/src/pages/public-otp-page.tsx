import * as React from "react";
import { Link, useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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

const isSafeHttpUrl = (url?: string | null): boolean => {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:";
  } catch {
    return false;
  }
};

export const PublicOtpPage = () => {
  const [searchParams] = useSearchParams();
  const urlEmail = searchParams.get("email") || searchParams.get("mail") || "";
  const urlPin = searchParams.get("pin") || "";

  const [email, setEmail] = React.useState(urlEmail);
  const [pin, setPin] = React.useState(urlPin);
  const [loading, setLoading] = React.useState(false);
  const [autoRefresh, setAutoRefresh] = React.useState(
    Boolean(urlEmail && urlPin)
  );
  const [result, setResult] = React.useState<{
    key: string;
    data: OtpResult;
  } | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [scheduleVersion, reschedule] = React.useReducer(value => value + 1, 0);
  const request = React.useRef<AbortController | null>(null);
  const sequence = React.useRef(0);
  const nextRequestAt = React.useRef(0);
  const failureCount = React.useRef(0);
  const mounted = React.useRef(true);
  const credentialsKey = `${email.trim().toLowerCase()}\0${pin.trim()}`;
  const currentKey = React.useRef(credentialsKey);
  const data = result?.key === credentialsKey ? result.data : null;
  const [copied, setCopied] = React.useState(false);
  const [copiedAccount, setCopiedAccount] = React.useState(false);
  const [showBody, setShowBody] = React.useState(false);
  const urlKey = `${urlEmail}\0${urlPin}`;
  const [previousUrl, setPreviousUrl] = React.useState(urlKey);

  // Reset URL-derived state during the render that observes navigation, so an
  // old mailbox is never committed alongside the new URL.
  if (previousUrl !== urlKey) {
    setPreviousUrl(urlKey);
    setEmail(urlEmail);
    setPin(urlPin);
    setAutoRefresh(Boolean(urlEmail && urlPin));
    setResult(null);
    setError(null);
    setLoading(false);
    setCopied(false);
    setShowBody(false);
  }

  React.useEffect(() => {
    if (urlPin && typeof window !== "undefined" && window.location) {
      try {
        const cleanParams = new URLSearchParams(window.location.search);
        cleanParams.delete("pin");
        const newSearch = cleanParams.toString();
        const newUrl =
          window.location.pathname + (newSearch ? `?${newSearch}` : "");
        window.history.replaceState({}, document.title, newUrl);
      } catch {
        // Some embedded browsers disallow history updates; requests still use a header.
      }
    }
  }, [urlEmail, urlPin]);

  React.useLayoutEffect(() => {
    currentKey.current = credentialsKey;
    sequence.current++;
    request.current?.abort();
    request.current = null;
  }, [credentialsKey]);

  const clearMailbox = () => {
    sequence.current++;
    request.current?.abort();
    request.current = null;
    setResult(null);
    setError(null);
    setLoading(false);
    setCopied(false);
    setShowBody(false);
  };

  React.useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      request.current?.abort();
    };
  }, []);

  const fetchOtp = React.useCallback(async () => {
    const targetMail = email.trim().toLowerCase();
    const targetPin = pin.trim();

    if (!targetMail) {
      toast.error("Vui lòng nhập địa chỉ email");
      return;
    }
    if (!targetPin) {
      toast.error("Vui lòng nhập mã PIN bảo mật");
      return;
    }

    // Share the cooldown between automatic and manual refreshes, including
    // credential changes. Eight seconds leaves room within the 10/min budget.
    if (request.current) return;
    if (Date.now() < nextRequestAt.current) {
      setError("Vui lòng chờ đến lần cập nhật tiếp theo.");
      return;
    }

    const controller = new AbortController();
    request.current = controller;
    const requestId = ++sequence.current;
    const key = credentialsKey;
    const isCurrent = () =>
      mounted.current &&
      requestId === sequence.current &&
      key === currentKey.current;
    nextRequestAt.current = Date.now() + 8000;
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `/api/public/otp?email=${encodeURIComponent(targetMail)}`,
        {
          signal: controller.signal,
          cache: "no-store",
          headers: {
            "X-Mailbox-Pin": targetPin,
          },
        }
      );
      if (!isCurrent()) return;
      if (response.status === 429) {
        const retryAfter = response.headers.get("Retry-After");
        const seconds = retryAfter?.trim() ? Number(retryAfter) : NaN;
        const retryAt = Number.isFinite(seconds)
          ? Date.now() + Math.max(0, seconds) * 1000
          : Date.parse(retryAfter ?? "");
        nextRequestAt.current = Math.max(
          Date.now() + 8000,
          Number.isFinite(retryAt) ? retryAt : Date.now() + 60000
        );
        setResult(null);
        setError("Đã đạt giới hạn truy cập. Tự động chờ trước khi thử lại.");
        return;
      }

      let result: OtpResult | null = null;
      try {
        result = (await response.json()) as OtpResult;
      } catch {
        // If response is not valid JSON (e.g. proxy HTML 502/503), result stays null
      }
      if (!isCurrent()) return;

      if (!response.ok || !result || !result.ok) {
        failureCount.current++;
        nextRequestAt.current =
          Date.now() +
          Math.min(60000, 8000 * 2 ** Math.min(failureCount.current, 3));
        setResult(null);
        setError(
          result?.error ||
            (response.status >= 500
              ? "Không thể kết nối dịch vụ thư trực tiếp. Vui lòng thử lại sau."
              : "Không thể lấy thông tin OTP")
        );
      } else {
        failureCount.current = 0;
        setResult({ key, data: result });
      }
    } catch {
      if (!isCurrent()) return;
      failureCount.current++;
      nextRequestAt.current =
        Date.now() +
        Math.min(60000, 8000 * 2 ** Math.min(failureCount.current, 3));
      setResult(null);
      setError("Lỗi kết nối máy chủ. Chưa thể cập nhật hộp thư.");
    } finally {
      if (isCurrent()) {
        request.current = null;
        setLoading(false);
        reschedule();
      }
    }
  }, [email, pin, credentialsKey]);

  // Schedule only after the previous request settles; manual refresh uses the
  // same gate and a 429 cooldown survives mailbox/PIN changes.
  React.useEffect(() => {
    if (!autoRefresh || !email.trim() || !pin.trim() || request.current) return;
    const timer = setTimeout(
      () => void fetchOtp(),
      Math.max(0, nextRequestAt.current - Date.now())
    );
    return () => clearTimeout(timer);
  }, [autoRefresh, email, pin, fetchOtp, scheduleVersion]);

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
            Tra Cứu Mã OTP Hộp Thư
          </h1>
          <p className="text-sm text-muted-foreground">
            Nhập email và mã PIN bảo mật để lấy mã xác thực hoặc link đăng nhập mới
            nhất.
          </p>
        </div>

        {/* Input Card */}
        <Card className="border border-border/80 shadow-md">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-medium">
              Thông tin hòm thư
            </CardTitle>
            <CardDescription className="text-xs">
              Mã PIN do người tạo hộp thư thiết lập tại trang quản lý. Hệ thống giới hạn 10 lần tra cứu/phút/hộp thư và 30 lần/phút/IP.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">
                Địa chỉ Email
              </label>
              <Input
                aria-label="Địa chỉ Email"
                type="email"
                placeholder="ví dụ: user01@domain.com"
                value={email}
                onChange={e => {
                  clearMailbox();
                  setEmail(e.target.value);
                }}
                className="font-mono text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">
                Mã PIN bảo mật
              </label>
              <Input
                aria-label="Mã PIN bảo mật"
                type="password"
                placeholder="ví dụ: 827192"
                value={pin}
                onChange={e => {
                  clearMailbox();
                  setPin(e.target.value);
                }}
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
                <span>Tự động cập nhật mỗi 8 giây khi máy chủ cho phép</span>
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
                  onClick={() => void fetchOtp()}
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

        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        {/* Results display */}
        {data && (
          <div className="space-y-4 animate-in fade-in duration-300">
            {!data.hasEmails ? (
              <Card className="border border-dashed border-amber-500/40 bg-amber-500/5">
                <CardContent className="pt-6 text-center space-y-2">
                  <div className="text-2xl">⏳</div>
                  <h3 className="font-semibold text-sm text-foreground">
                    Đang chờ thư xác thực mới...
                  </h3>
                  <p className="text-xs text-muted-foreground max-w-md mx-auto">
                    {data.message ||
                      "Chưa có thư mới nào gửi đến. Vui lòng bấm gửi mã OTP trên dịch vụ bạn đang thao tác, sau đó quay lại trang này (hệ thống sẽ tự nhận mã khi có thư đến)."}
                  </p>
                  {data.isLocalDevDomain && (
                    <div className="mt-4 p-3 rounded-lg bg-amber-500/15 border border-amber-500/30 text-xs text-amber-700 dark:text-amber-300 text-left max-w-lg mx-auto space-y-1.5">
                      <div className="font-semibold flex items-center gap-1.5">
                        ⚠️ Nguyên nhân chưa nhận được mã:
                      </div>
                      <div>
                        Email này mang đuôi <code>@spinupmail.dev</code> (tên
                        miền thử nghiệm nội bộ local). Máy chủ gửi thư từ internet
                        không thể chuyển tiếp thư tới tên miền thử nghiệm nội bộ này.
                      </div>
                      <div className="pt-1 font-medium">
                        👉 <strong>Giải pháp:</strong> Đăng nhập và tạo hộp thư với tên miền công khai tại{" "}
                        <Link
                          to="/addresses"
                          className="underline font-bold text-primary"
                        >
                          Trang Quản Lý Hộp Thư (/addresses)
                        </Link>
                        . Lưu ý: dịch vụ nhận thư phụ thuộc vào nhà cung cấp trực tiếp; hệ thống không cam kết tỷ lệ 100% hay bảo đảm đăng ký thành công trên mọi dịch vụ bên thứ ba.
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            ) : (
              <Card className="border-2 border-primary/40 bg-card shadow-lg">
                <CardHeader className="pb-3 border-b border-border/40">
                  <div className="flex items-center justify-between">
                    <Badge
                      variant="outline"
                      className="text-xs font-mono text-emerald-600 dark:text-emerald-400 border-emerald-500/40 bg-emerald-500/10"
                    >
                      ✓ Đã nhận thư mới
                    </Badge>
                    <span className="text-[11px] text-muted-foreground">
                      {data.latest?.receivedAt
                        ? new Date(data.latest.receivedAt).toLocaleTimeString(
                            "vi-VN"
                          )
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
                      Không tìm thấy mã số ngắn trong email. Vui lòng xem link
                      hoặc nội dung bên dưới.
                    </div>
                  )}

                  {/* Magic Link / Direct Confirmation Link */}
                  {isSafeHttpUrl(data.latest?.magicLink) && (
                    <div className="p-3.5 rounded-lg border border-blue-500/30 bg-blue-500/10 space-y-2 text-center">
                      <p className="text-xs font-medium text-blue-600 dark:text-blue-400">
                        🔗 Phát hiện đường link kích hoạt / đăng nhập:
                      </p>
                      <a
                        href={data.latest!.magicLink!}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-block w-full sm:w-auto px-4 py-2 rounded-md bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors"
                      >
                        Mở link kích hoạt tài khoản ↗
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
                      {showBody
                        ? "Thu gọn nội dung email ▲"
                        : "Xem toàn bộ nội dung email nhận được ▼"}
                    </button>

                    {showBody && (
                      <div className="mt-3 p-3 rounded-md bg-muted/50 border border-border/60 text-xs text-foreground font-mono whitespace-pre-wrap max-h-72 overflow-y-auto">
                        {data.latest?.bodyText ||
                          (data.latest?.bodyHtml
                            ? data.latest.bodyHtml
                                .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, " ")
                                .replace(
                                  /<script[^>]*>[\s\S]*?<\/script>/gi,
                                  " "
                                )
                                .replace(/<[^>]+>/g, " ")
                                .replace(/&nbsp;/g, " ")
                                .trim()
                            : "(Không có nội dung)")}
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
          <p className="font-semibold text-foreground">
            💡 Dành cho người quản lý / chia sẻ hộp thư:
          </p>
          <p>
            Hộp thư cần được tạo bởi người dùng đăng nhập tại{" "}
            <Link to="/addresses" className="underline font-medium text-primary">
              Trang Quản Lý Hộp Thư (/addresses)
            </Link>{" "}
            với tùy chọn tạo PIN bảo mật (lưu PIN ngay khi tạo, không hiển thị lại).
            <br />
            Bạn có thể gửi cho người nhận link tra cứu an toàn dạng:
            <br />
            <code className="text-primary font-mono text-[11px] block mt-1 p-1 bg-muted rounded truncate">
              {window.location.origin}/otp?mail={email || "user01@domain.com"}
            </code>
            (Người nhận cần nhập thêm mã PIN bí mật được cấp riêng. Giới hạn: 10 lần/phút/hộp thư, 30 lần/phút/IP).
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
