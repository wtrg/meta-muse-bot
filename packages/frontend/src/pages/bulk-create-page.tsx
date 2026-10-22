import { Link } from "react-router";
import {
  ExternalLink,
  Mail,
  Key,
  ShieldCheck,
  Inbox,
  ArrowRight,
  Bot,
  AlertTriangle,
} from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export const BulkCreatePage = () => {
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
                SpinupMail • Quản Lý Hộp Thư & Cổng OTP
              </h1>
              <p className="text-xs text-muted-foreground">
                Hệ thống xác thực hộp thư và tra cứu mã bảo mật có phân quyền
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              to="/muse"
              className={buttonVariants({ variant: "default", size: "sm", className: "bg-violet-600 hover:bg-violet-700 text-white font-bold" })}
            >
              <Bot className="size-3.5 mr-1.5" />
              Giao Diện Muse Bot
            </Link>

            <Link
              to="/otp"
              target="_blank"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <Key className="size-3.5 mr-1.5" />
              Cổng Tra Cứu OTP
              <ExternalLink className="size-3 ml-1" />
            </Link>

            <Link
              to="/addresses"
              className={buttonVariants({ size: "sm", className: "bg-primary text-primary-foreground font-medium" })}
            >
              <Inbox className="size-3.5 mr-1.5" />
              Quản Lý Hộp Thư Đăng Nhập
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 pt-8 space-y-6">
        <Card className="border-amber-500/40 bg-amber-500/5 shadow-md">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="size-10 rounded-xl bg-amber-500/15 text-amber-600 dark:text-amber-400 flex items-center justify-center">
                <AlertTriangle className="size-5" />
              </div>
              <div>
                <CardTitle className="text-lg">
                  Cổng Tạo Hàng Loạt Ẩn Danh Đã Bị Vô Hiệu Hóa (Chính Sách Bảo Mật A01, A04, A05)
                </CardTitle>
                <CardDescription className="mt-1 text-sm text-muted-foreground">
                  Để bảo vệ quyền riêng tư người dùng và ngăn ngừa truy cập chéo trái phép vào hộp thư của người khác, các API công khai không xác thực đã được gỡ bỏ hoàn toàn khỏi hệ thống.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
              <div className="p-4 rounded-lg border border-border bg-card space-y-2">
                <div className="font-semibold flex items-center gap-1.5 text-foreground">
                  <ShieldCheck className="size-4 text-emerald-500" />
                  Đóng /recent-otps (A01)
                </div>
                <p className="text-xs text-muted-foreground">
                  Loại bỏ endpoint quét toàn bộ OTP không cần phân quyền để ngăn chặn kẻ tấn công đọc lén mã xác thực của các tài khoản khác.
                </p>
              </div>

              <div className="p-4 rounded-lg border border-border bg-card space-y-2">
                <div className="font-semibold flex items-center gap-1.5 text-foreground">
                  <ShieldCheck className="size-4 text-emerald-500" />
                  Đóng /bulk-create (A04)
                </div>
                <p className="text-xs text-muted-foreground">
                  Ngăn chặn anonymous caller tự động tạo hàng loạt tài khoản quản trị và tổ chức giả lập vào cơ sở dữ liệu.
                </p>
              </div>

              <div className="p-4 rounded-lg border border-border bg-card space-y-2">
                <div className="font-semibold flex items-center gap-1.5 text-foreground">
                  <ShieldCheck className="size-4 text-emerald-500" />
                  Đóng /auto-login (A05)
                </div>
                <p className="text-xs text-muted-foreground">
                  Gỡ bỏ hoàn toàn thông tin đăng nhập cố định mã hóa cứng trong mã nguồn, bắt buộc xác thực phiên chính danh.
                </p>
              </div>
            </div>

            <div className="rounded-lg border border-border/80 bg-muted/30 p-4 space-y-2 text-xs text-muted-foreground">
              <div className="font-semibold text-foreground text-sm">
                📋 Quy trình tạo và sử dụng hộp thư chính thức:
              </div>
              <ul className="list-disc pl-4 space-y-1">
                <li>
                  <strong>Tạo hộp thư có xác thực:</strong> Đăng nhập tài khoản và tạo từng hộp thư trong tổ chức tại{" "}
                  <Link to="/addresses" className="underline font-medium text-primary">
                    Trang Quản Lý Hộp Thư (/addresses)
                  </Link>
                  .
                </li>
                <li>
                  <strong>Mã PIN bảo mật một lần:</strong> Bật tùy chọn &quot;Generate a mailbox PIN&quot; khi tạo. Mã PIN chỉ hiển thị một lần duy nhất sau khi tạo và cần được tự lưu lại.
                </li>
                <li>
                  <strong>Giới hạn tra cứu OTP:</strong> Cổng tra cứu công khai{" "}
                  <Link to="/otp" className="underline font-medium text-primary">
                    /otp
                  </Link>{" "}
                  giới hạn 10 lượt/phút cho mỗi hộp thư và 30 lượt/phút cho mỗi IP để chống tấn công đoán mã.
                </li>
                <li>
                  <strong>Khả năng nhận thư:</strong> Việc đồng bộ thư phụ thuộc vào nhà cung cấp trực tiếp; hệ thống không đảm bảo 100% hay cam kết đăng ký thành công trên các dịch vụ bên thứ ba.
                </li>
              </ul>
            </div>

            <div className="pt-2 flex flex-wrap gap-3">
              <Link
                to="/addresses"
                className={buttonVariants({ variant: "default", className: "font-medium" })}
              >
                <Inbox className="size-4 mr-2" />
                Đến Trang Quản Lý Hộp Thư Chính Thức (/addresses)
                <ArrowRight className="size-4 ml-1.5" />
              </Link>

              <Link
                to="/otp"
                className={buttonVariants({ variant: "outline" })}
              >
                <Key className="size-4 mr-2" />
                Đến Cổng Tra Cứu OTP Có Mã PIN (/otp)
              </Link>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
};
