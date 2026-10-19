import * as React from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import {
  Copy,
  Check,
  ExternalLink,
  RefreshCw,
  Mail,
  Key,
  ShieldCheck,
  Zap,
  Search,
  Inbox,
  ArrowRight,
  Sparkles,
  Bot,
} from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Badge } from "@/components/ui/badge";

type CreatedItem = {
  address: string;
  pin: string;
  otpUrl: string;
  formatted: string;
};

type RecentOtpItem = {
  id: string;
  address: string;
  pin: string;
  from: string | null;
  subject: string | null;
  otp: string | null;
  magicLink: string | null;
  receivedAt: string | null;
};

export const BulkCreatePage = () => {
  // Bulk creation form state
  const [prefix, setPrefix] = React.useState("muse");
  const [count, setCount] = React.useState(10);
  const [domain, setDomain] = React.useState("spinupmail.dev");
  const [availableDomains, setAvailableDomains] = React.useState<string[]>([
    "spinupmail.dev",
    "mail.muse.ai",
    "muse-mail.com",
  ]);
  const [isGenerating, setIsGenerating] = React.useState(false);
  const [createdItems, setCreatedItems] = React.useState<CreatedItem[]>([]);
  const [allFormatted, setAllFormatted] = React.useState<string>("");

  // Live scanner state
  const [recentOtps, setRecentOtps] = React.useState<RecentOtpItem[]>([]);
  const [isLoadingOtps, setIsLoadingOtps] = React.useState(false);
  const [searchFilter, setSearchFilter] = React.useState("");
  const [autoRefresh, setAutoRefresh] = React.useState(true);
  const [copiedKey, setCopiedKey] = React.useState<string | null>(null);

  // Copy helper
  const handleCopy = (text: string, key: string, label: string = "Đã sao chép") => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    toast.success(label);
    setTimeout(() => {
      setCopiedKey(prev => (prev === key ? null : prev));
    }, 2000);
  };

  // Fetch available domains on mount
  React.useEffect(() => {
    fetch("/api/public/domains")
      .then(r => r.json())
      .then(data => {
        if (data.ok && Array.isArray(data.domains) && data.domains.length > 0) {
          setAvailableDomains(data.domains);
          setDomain(data.domains[0]);
        }
      })
      .catch(() => {});
  }, []);

  // Fetch recent OTPs across all inboxes
  const fetchRecentOtps = React.useCallback(async () => {
    try {
      setIsLoadingOtps(true);
      const res = await fetch("/api/public/recent-otps");
      const data = await res.json();
      if (data.ok && Array.isArray(data.items)) {
        setRecentOtps(data.items);
      }
    } catch {
      // Ignore polling errors
    } finally {
      setIsLoadingOtps(false);
    }
  }, []);

  // Polling loop for live OTP scanner
  React.useEffect(() => {
    fetchRecentOtps();
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchRecentOtps();
    }, 3000);

    return () => clearInterval(interval);
  }, [fetchRecentOtps, autoRefresh]);

  // Handle bulk create submission
  const handleBulkCreate = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    try {
      setIsGenerating(true);
      const res = await fetch("/api/public/bulk-create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prefix: prefix.trim() || "muse",
          count: Number(count) || 10,
          domain,
        }),
      });

      const data = await res.json();
      if (data.ok) {
        const origin = window.location.origin;
        const normalized = (data.items || []).map((it: any) => ({
          ...it,
          otpUrl: `${origin}/otp?mail=${encodeURIComponent(it.address)}&pin=${encodeURIComponent(it.pin)}`,
        }));
        setCreatedItems(normalized);
        const formatted = normalized.map((it: any) => `${it.address} | PIN: ${it.pin} | ${it.otpUrl}`).join("\n");
        setAllFormatted(formatted);
        toast.success(`Đã tạo thành công ${data.count} email mới!`);
      } else {
        toast.error(data.error || "Không thể tạo email.");
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Lỗi khi gọi máy chủ");
    } finally {
      setIsGenerating(false);
    }
  };

  // Filtered recent OTPs
  const filteredOtps = React.useMemo(() => {
    if (!searchFilter.trim()) return recentOtps;
    const query = searchFilter.toLowerCase();
    return recentOtps.filter(
      item =>
        item.address.toLowerCase().includes(query) ||
        (item.subject && item.subject.toLowerCase().includes(query)) ||
        (item.otp && item.otp.includes(query)) ||
        (item.from && item.from.toLowerCase().includes(query))
    );
  }, [recentOtps, searchFilter]);

  return (
    <div className="min-h-screen bg-background text-foreground pb-16">
      {/* Top Navbar */}
      <header className="border-b border-border/60 bg-card/60 backdrop-blur sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="size-9 rounded-xl bg-primary/10 text-primary flex items-center justify-center font-bold text-lg shadow-sm">
              <Mail className="size-5 text-primary" />
            </div>
            <div>
              <h1 className="font-bold text-base leading-tight">
                SpinupMail • Reg Mail & Quét OTP Muse.ai / Meta
              </h1>
              <p className="text-xs text-muted-foreground">
                Tự động trích xuất mã xác minh & quản lý tài khoản
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              to="/muse-bot"
              className={buttonVariants({ variant: "default", size: "sm", className: "bg-violet-600 hover:bg-violet-700 text-white font-bold" })}
            >
              <Bot className="size-3.5 mr-1.5" />
              Bot Tự Động Reg Muse.ai
            </Link>

            <Link
              to="/otp"
              target="_blank"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <Key className="size-3.5 mr-1.5" />
              Trang Lấy OTP Khách
              <ExternalLink className="size-3 ml-1" />
            </Link>

            <Link
              to="/addresses"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <Inbox className="size-3.5 mr-1.5" />
              Quản Trị Dashboard
            </Link>

            <a
              href="/api/public/auto-login"
              className={buttonVariants({ size: "sm", className: "bg-primary text-primary-foreground font-medium" })}
            >
              <Zap className="size-3.5 mr-1.5" />
              1-Click Đăng Nhập
            </a>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 pt-6 space-y-8">
        {/* SECTION 1: Bulk Generator Card */}
        <Card className="border-border/80 shadow-md">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-xl flex items-center gap-2">
                  <Sparkles className="size-5 text-amber-500" />
                  Tạo Email Hàng Loạt (Bulk Email Generator)
                </CardTitle>
                <CardDescription className="mt-1">
                  Mỗi email được gán kèm 1 Mã PIN bảo mật riêng để khách hàng tự vào lấy OTP mà không lộ thư của người khác.
                </CardDescription>
              </div>
              <Badge variant="outline" className="px-3 py-1 text-xs font-medium border-primary/30 text-primary">
                Tối đa 50 mail / lần bấm
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <form onSubmit={handleBulkCreate} className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1.5">
                  Tiền tố Email (Prefix)
                </label>
                <Input
                  value={prefix}
                  onChange={e => setPrefix(e.target.value)}
                  placeholder="muse, acc, fb..."
                  className="bg-card"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1.5">
                  Tên miền (Domain)
                </label>
                <select
                  value={domain}
                  onChange={e => setDomain(e.target.value)}
                  className="w-full h-9 rounded-md border border-input bg-card px-3 text-xs sm:text-sm focus:outline-none focus:ring-1 focus:ring-ring font-medium"
                >
                  {availableDomains.map(d => (
                    <option key={d} value={d}>
                      {d === "maxxspace.com" ? `@${d} (🟢 Nhận mail THẬT Muse.ai)` : `@${d} (🟡 Local dev only)`}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1.5">
                  Số lượng cần tạo
                </label>
                <div className="flex items-center gap-1.5">
                  {[5, 10, 20, 50].map(n => (
                    <Button
                      key={n}
                      type="button"
                      variant={count === n ? "default" : "outline"}
                      size="sm"
                      onClick={() => setCount(n)}
                      className="flex-1 text-xs"
                    >
                      {n}
                    </Button>
                  ))}
                </div>
              </div>

              <div>
                <Button
                  type="submit"
                  disabled={isGenerating}
                  className="w-full font-semibold shadow-sm"
                >
                  {isGenerating ? (
                    <>
                      <Spinner className="size-4 mr-2" />
                      Đang khởi tạo {count} mail...
                    </>
                  ) : (
                    <>
                      <Zap className="size-4 mr-2 text-amber-300" />
                      Tạo {count} Email Ngay
                    </>
                  )}
                </Button>
              </div>
            </form>

            <div className="p-3.5 rounded-lg bg-emerald-500/10 border border-emerald-500/25 text-xs text-emerald-800 dark:text-emerald-300 flex items-start gap-2.5">
              <ShieldCheck className="size-4 shrink-0 mt-0.5 text-emerald-500" />
              <div className="space-y-1">
                <div className="font-semibold text-foreground">💡 Lưu ý quan trọng để nhận mã từ Muse.ai / Meta:</div>
                <div>
                  Hãy chọn tên miền <strong>@maxxspace.com</strong> khi tạo email. Đây là hộp thư THẬT trên internet được hệ thống kết nối tự động, đảm bảo Muse.ai gửi mã OTP về thành công 100%. Đuôi <code>@spinupmail.dev</code> chỉ là tên miền thử nghiệm nội bộ local nên Muse.ai không thể gửi tới máy bạn được.
                </div>
              </div>
            </div>

            {/* Generated Output Textarea & Table */}
            {createdItems.length > 0 && (
              <div className="pt-4 border-t border-border/70 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                      <Check className="size-4" />
                      Đã tạo thành công {createdItems.length} địa chỉ:
                    </span>
                  </div>

                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      handleCopy(
                        allFormatted,
                        "copy-all",
                        "Đã sao chép toàn bộ danh sách (Email | PIN | Link OTP)!"
                      )
                    }
                    className="text-xs"
                  >
                    {copiedKey === "copy-all" ? (
                      <Check className="size-3.5 mr-1.5 text-emerald-500" />
                    ) : (
                      <Copy className="size-3.5 mr-1.5" />
                    )}
                    Sao Chép Toàn Bộ (Dạng Text)
                  </Button>
                </div>

                {/* Textarea for bulk export */}
                <textarea
                  readOnly
                  rows={4}
                  value={allFormatted}
                  className="w-full rounded-md border border-border bg-muted/40 p-3 font-mono text-xs leading-relaxed focus:outline-none"
                />

                {/* Table of created addresses */}
                <div className="border border-border/70 rounded-lg overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-muted/50 border-b border-border text-muted-foreground uppercase text-[10px] tracking-wider">
                      <tr>
                        <th className="py-2.5 px-3">#</th>
                        <th className="py-2.5 px-3">Địa Chỉ Email</th>
                        <th className="py-2.5 px-3">Mã PIN Bí Mật</th>
                        <th className="py-2.5 px-3">Link Khách Tự Lấy OTP</th>
                        <th className="py-2.5 px-3 text-right">Thao Tác</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {createdItems.map((item, idx) => (
                        <tr key={item.address} className="hover:bg-muted/30 transition-colors">
                          <td className="py-2.5 px-3 text-muted-foreground">{idx + 1}</td>
                          <td className="py-2.5 px-3 font-mono font-medium">{item.address}</td>
                          <td className="py-2.5 px-3">
                            <span className="font-mono bg-amber-500/10 text-amber-600 dark:text-amber-400 px-2 py-0.5 rounded font-bold">
                              {item.pin}
                            </span>
                          </td>
                          <td className="py-2.5 px-3">
                            <a
                              href={item.otpUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="text-primary hover:underline flex items-center gap-1 font-mono text-[11px]"
                            >
                              /otp?mail={item.address}&pin={item.pin}
                              <ExternalLink className="size-3" />
                            </a>
                          </td>
                          <td className="py-2.5 px-3 text-right space-x-1.5">
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 px-2 text-xs"
                              onClick={() => handleCopy(item.address, `addr-${idx}`, "Đã chép Email")}
                            >
                              {copiedKey === `addr-${idx}` ? (
                                <Check className="size-3 text-emerald-500" />
                              ) : (
                                <Copy className="size-3" />
                              )}
                              <span className="ml-1">Mail</span>
                            </Button>

                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 px-2 text-xs"
                              onClick={() =>
                                handleCopy(
                                  `${item.address} | PIN: ${item.pin} | ${item.otpUrl}`,
                                  `full-${idx}`,
                                  "Đã chép Email + PIN + Link"
                                )
                              }
                            >
                              {copiedKey === `full-${idx}` ? (
                                <Check className="size-3 text-emerald-500" />
                              ) : (
                                <Copy className="size-3" />
                              )}
                              <span className="ml-1">Cả bộ</span>
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* SECTION 2: Live Scanner for all inboxes (Quét Tất Cả Hòm Thư & Bắt OTP Meta/Muse) */}
        <Card className="border-border/80 shadow-md">
          <CardHeader>
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <CardTitle className="text-xl flex items-center gap-2">
                  <ShieldCheck className="size-5 text-emerald-500" />
                  Bảng Quét Toàn Bộ Hòm Thư & Bắt OTP Trực Tiếp (Meta / Muse.ai)
                </CardTitle>
                <CardDescription className="mt-1">
                  Hệ thống tự động lắng nghe và trích xuất mã OTP từ tất cả email gửi về hòm thư hệ thống theo thời gian thực.
                </CardDescription>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setAutoRefresh(prev => !prev)}
                  className={`text-xs ${autoRefresh ? "border-emerald-500/40 text-emerald-500" : ""}`}
                >
                  <span className={`size-2 rounded-full mr-2 ${autoRefresh ? "bg-emerald-500 animate-pulse" : "bg-muted-foreground"}`} />
                  {autoRefresh ? "Đang tự quét (3s)" : "Tạm dừng quét"}
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={fetchRecentOtps}
                  disabled={isLoadingOtps}
                  className="text-xs"
                >
                  <RefreshCw className={`size-3.5 mr-1.5 ${isLoadingOtps ? "animate-spin" : ""}`} />
                  Làm mới
                </Button>
              </div>
            </div>

            {/* Search Filter */}
            <div className="pt-3">
              <div className="relative max-w-md">
                <Search className="size-4 absolute left-3 top-2.5 text-muted-foreground" />
                <Input
                  value={searchFilter}
                  onChange={e => setSearchFilter(e.target.value)}
                  placeholder="Lọc theo địa chỉ email hoặc mã OTP..."
                  className="pl-9 h-9 text-xs bg-card"
                />
              </div>
            </div>
          </CardHeader>

          <CardContent>
            {filteredOtps.length === 0 ? (
              <div className="text-center py-12 border border-dashed border-border rounded-lg bg-muted/10 space-y-3">
                <Mail className="size-8 mx-auto text-muted-foreground/60" />
                <div className="text-sm font-medium">Chưa có email nào trong hòm thư</div>
                <p className="text-xs text-muted-foreground max-w-md mx-auto">
                  Hãy gửi mã đăng ký/đăng nhập từ Muse.ai hoặc Meta đến bất kỳ email nào bạn vừa tạo. Mã OTP sẽ hiển thị tự động tại đây sau 2-3 giây.
                </p>
              </div>
            ) : (
              <div className="border border-border/70 rounded-lg overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-muted/50 border-b border-border text-muted-foreground uppercase text-[10px] tracking-wider">
                    <tr>
                      <th className="py-2.5 px-3">Hòm Thư Nhận</th>
                      <th className="py-2.5 px-3">Mã OTP Bắt Được</th>
                      <th className="py-2.5 px-3">Tiêu Đề Thư</th>
                      <th className="py-2.5 px-3">Người Gửi</th>
                      <th className="py-2.5 px-3">Thời Gian</th>
                      <th className="py-2.5 px-3 text-right">Hành Động</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {filteredOtps.map(item => (
                      <tr key={item.id} className="hover:bg-muted/30 transition-colors">
                        <td className="py-3 px-3">
                          <div className="font-mono font-medium">{item.address}</div>
                          {item.pin && (
                            <div className="text-[10px] text-muted-foreground mt-0.5">
                              PIN: <span className="font-mono text-amber-500">{item.pin}</span>
                            </div>
                          )}
                        </td>

                        <td className="py-3 px-3">
                          {item.otp ? (
                            <button
                              type="button"
                              onClick={() => handleCopy(item.otp!, `otp-${item.id}`, `Đã sao chép OTP: ${item.otp}`)}
                              className="group flex items-center gap-1.5 bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-600 dark:text-emerald-400 font-mono text-base font-bold px-2.5 py-1 rounded-md border border-emerald-500/30 transition-colors"
                            >
                              <span>{item.otp}</span>
                              {copiedKey === `otp-${item.id}` ? (
                                <Check className="size-3.5 text-emerald-500" />
                              ) : (
                                <Copy className="size-3.5 opacity-60 group-hover:opacity-100" />
                              )}
                            </button>
                          ) : item.magicLink ? (
                            <a
                              href={item.magicLink}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-[11px] bg-primary/10 text-primary px-2 py-1 rounded border border-primary/20 hover:bg-primary/20"
                            >
                              <span>Mở Link Đăng Nhập</span>
                              <ExternalLink className="size-3" />
                            </a>
                          ) : (
                            <span className="text-muted-foreground italic text-[11px]">Không có OTP</span>
                          )}
                        </td>

                        <td className="py-3 px-3 max-w-[260px] truncate" title={item.subject || ""}>
                          <span className="font-medium">{item.subject || "(Không tiêu đề)"}</span>
                        </td>

                        <td className="py-3 px-3 text-muted-foreground max-w-[160px] truncate" title={item.from || ""}>
                          {item.from || "Không rõ"}
                        </td>

                        <td className="py-3 px-3 text-muted-foreground whitespace-nowrap">
                          {item.receivedAt ? new Date(item.receivedAt).toLocaleTimeString("vi-VN") : "Vừa xong"}
                        </td>

                        <td className="py-3 px-3 text-right">
                          {item.pin ? (
                            <a
                              href={`/otp?mail=${encodeURIComponent(item.address)}&pin=${encodeURIComponent(item.pin)}`}
                              target="_blank"
                              rel="noreferrer"
                              className={buttonVariants({ size: "sm", variant: "outline", className: "h-7 text-xs" })}
                            >
                              <span>Mở trang OTP</span>
                              <ExternalLink className="size-3 ml-1" />
                            </a>
                          ) : (
                            <Link
                              to="/inbox"
                              className={buttonVariants({ size: "sm", variant: "outline", className: "h-7 text-xs" })}
                            >
                              <span>Xem thư</span>
                              <ArrowRight className="size-3 ml-1" />
                            </Link>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
};
