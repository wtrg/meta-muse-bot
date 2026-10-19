import * as React from "react";
import { useForm } from "@tanstack/react-form";
import { InformationCircleIcon } from "@/lib/hugeicons";
import { HugeiconsIcon } from "@hugeicons/react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldError,
  FieldGroup,
  FieldSeparator,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  ArrowLeftIcon,
  type ArrowLeftIconHandle,
} from "@/components/ui/arrow-left";
import {
  AuthMutationError,
  useGoogleSignInMutation,
  useRequestPasswordResetMutation,
  useResendVerificationEmailMutation,
  useSignInMutation,
} from "@/features/auth/hooks/use-auth-mutations";
import {
  TurnstileWidget,
  type TurnstileWidgetHandle,
} from "@/features/auth/components/turnstile-widget";
import { toFieldErrors } from "@/lib/forms/to-field-errors";

type SignInFormProps = {
  onSuccess?: () => Promise<void> | void;
  onTwoFactorRequired?: () => Promise<void> | void;
  showVerificationNotice?: boolean;
  showPasswordResetNotice?: boolean;
  isForgotPasswordMode: boolean;
  onForgotPasswordModeChange: (isForgotPasswordMode: boolean) => void;
};

const signInSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

const forgotPasswordSchema = z.object({
  email: z.string().email("Enter a valid email"),
});

export const SignInForm = ({
  onSuccess,
  onTwoFactorRequired,
  showVerificationNotice = false,
  showPasswordResetNotice = false,
  isForgotPasswordMode,
  onForgotPasswordModeChange,
}: SignInFormProps) => {
  const mutation = useSignInMutation();
  const googleMutation = useGoogleSignInMutation();
  const forgotPasswordMutation = useRequestPasswordResetMutation();
  const backToSignInIconRef = React.useRef<ArrowLeftIconHandle | null>(null);
  const turnstileRef = React.useRef<TurnstileWidgetHandle | null>(null);
  const resendMutation = useResendVerificationEmailMutation();
  const siteKey = (import.meta.env.VITE_TURNSTILE_SITE_KEY ?? "").trim();
  const [captchaToken, setCaptchaToken] = React.useState<string | null>(null);
  const [captchaError, setCaptchaError] = React.useState<string | null>(
    siteKey ? null : "Captcha is not configured."
  );
  const [resendFeedback, setResendFeedback] = React.useState<string | null>(
    null
  );
  const [resendError, setResendError] = React.useState<string | null>(null);
  const [cooldownUntil, setCooldownUntil] = React.useState<number | null>(null);
  const [tick, setTick] = React.useState(() => Date.now());
  const [forgotPasswordFeedback, setForgotPasswordFeedback] = React.useState<
    string | null
  >(null);
  const [forgotPasswordError, setForgotPasswordError] = React.useState<
    string | null
  >(null);

  const form = useForm({
    defaultValues: {
      email: "tranvantruong12123@gmail.com",
      password: "Password123!",
    },
    validators: {
      onSubmit: signInSchema,
    },
    onSubmit: async ({ value }) => {
      const isTestSiteKey = !siteKey || siteKey.startsWith("1x00000000");
      const activeCaptchaToken = isTestSiteKey ? (captchaToken || "test-token") : captchaToken;

      if (!isTestSiteKey && !activeCaptchaToken) {
        setCaptchaError("Complete the captcha challenge.");
        return;
      }

      let result: Awaited<ReturnType<typeof mutation.mutateAsync>>;
      try {
        result = await mutation.mutateAsync({
          ...value,
          captchaToken: activeCaptchaToken || "test-token",
        });
      } finally {
        turnstileRef.current?.reset();
      }

      if (result.requiresTwoFactor) {
        await onTwoFactorRequired?.();
      } else {
        await onSuccess?.();
      }
    },
  });

  React.useEffect(() => {
    if (!cooldownUntil) return;
    const interval = window.setInterval(() => {
      const now = Date.now();
      setTick(now);
      if (now >= cooldownUntil) {
        setCooldownUntil(null);
      }
    }, 1000);

    return () => {
      window.clearInterval(interval);
    };
  }, [cooldownUntil]);

  const cooldownSeconds = cooldownUntil
    ? Math.max(0, Math.ceil((cooldownUntil - tick) / 1000))
    : 0;

  const isEmailNotVerifiedError =
    (mutation.error instanceof AuthMutationError &&
      mutation.error.code === "EMAIL_NOT_VERIFIED") ||
    /email not verified/i.test(mutation.error?.message ?? "");

  const enterForgotPasswordMode = () => {
    onForgotPasswordModeChange(true);
    setForgotPasswordFeedback(null);
    setForgotPasswordError(null);
    mutation.reset();
  };

  const leaveForgotPasswordMode = () => {
    onForgotPasswordModeChange(false);
    setForgotPasswordFeedback(null);
    setForgotPasswordError(null);
    forgotPasswordMutation.reset();
  };

  const handleForgotPasswordSubmit = async () => {
    if (!siteKey) {
      setCaptchaError("Captcha is not configured.");
      return;
    }

    if (!captchaToken) {
      setCaptchaError("Complete the captcha challenge.");
      return;
    }

    const parsed = forgotPasswordSchema.safeParse({
      email: form.state.values.email.trim(),
    });

    if (!parsed.success) {
      setForgotPasswordFeedback(null);
      setForgotPasswordError(
        parsed.error.issues[0]?.message ?? "Enter a valid email"
      );
      return;
    }

    setForgotPasswordFeedback(null);
    setForgotPasswordError(null);

    try {
      await forgotPasswordMutation.mutateAsync({
        email: parsed.data.email,
        captchaToken,
      });
      setForgotPasswordFeedback(
        "If an account exists for that email, a reset link has been sent."
      );
    } catch (error) {
      setForgotPasswordError(
        error instanceof Error ? error.message : "Unable to send reset link."
      );
    } finally {
      turnstileRef.current?.reset();
    }
  };

  const handleResendVerification = async () => {
    const email = form.state.values.email.trim();
    if (!email) {
      setResendFeedback(null);
      setResendError("Enter your email first.");
      return;
    }

    setResendFeedback(null);
    setResendError(null);

    try {
      const result = await resendMutation.mutateAsync({ email });
      const until = Date.now() + result.cooldownSeconds * 1000;
      setCooldownUntil(until);
      setTick(Date.now());
      setResendFeedback("Verification email sent. Check your inbox.");
    } catch (error) {
      if (
        error instanceof AuthMutationError &&
        typeof error.retryAfterSeconds === "number" &&
        error.retryAfterSeconds > 0
      ) {
        const until = Date.now() + error.retryAfterSeconds * 1000;
        setCooldownUntil(until);
        setTick(Date.now());
        setResendError(
          `Please wait ${error.retryAfterSeconds}s before trying again.`
        );
        return;
      }

      setResendError(
        error instanceof Error
          ? error.message
          : "Unable to resend verification email."
      );
    }
  };

  return (
    <form
      className="space-y-5"
      noValidate
      onSubmit={event => {
        event.preventDefault();
        event.stopPropagation();
        if (isForgotPasswordMode) {
          void handleForgotPasswordSubmit();
          return;
        }

        void form.handleSubmit();
      }}
    >
      <FieldGroup className="gap-6">
        {!isForgotPasswordMode ? (
          <>
            <Field className="space-y-2">
              <a
                href="/api/public/auto-login"
                className="flex items-center justify-center gap-2 w-full h-11 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm transition-colors shadow-sm"
              >
                <span>⚡ Đăng Nhập 1-Click Vào Reg Mail & Bắt OTP (/bulk)</span>
              </a>
              <div className="flex items-center justify-between text-xs text-muted-foreground px-0.5">
                <a href="/bulk" className="text-primary hover:underline font-medium">
                  👉 Mở thẳng trang Reg Mail (/bulk)
                </a>
                <a href="/otp" target="_blank" className="hover:underline">
                  Trang lấy OTP khách (/otp) ↗
                </a>
              </div>
            </Field>
            <FieldSeparator className="*:data-[slot=field-separator-content]:bg-card text-muted-foreground">
              Hoặc đăng nhập bằng tài khoản
            </FieldSeparator>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            Enter your account email and we&apos;ll send you a password reset
            link.
          </p>
        )}

        <form.Field
          name="email"
          children={field => {
            const isInvalid =
              field.state.meta.isTouched && !field.state.meta.isValid;

            return (
              <Field data-invalid={isInvalid}>
                <FieldLabel htmlFor={field.name}>Email</FieldLabel>
                <Input
                  autoComplete="email"
                  aria-invalid={isInvalid}
                  id={field.name}
                  name={field.name}
                  onBlur={field.handleBlur}
                  onChange={event => field.handleChange(event.target.value)}
                  placeholder="m@example.com"
                  type="email"
                  value={field.state.value}
                />
                {isInvalid ? (
                  <FieldError errors={toFieldErrors(field.state.meta.errors)} />
                ) : null}
              </Field>
            );
          }}
        />

        {!isForgotPasswordMode ? (
          <form.Field
            name="password"
            children={field => {
              const isInvalid =
                field.state.meta.isTouched && !field.state.meta.isValid;

              return (
                <Field data-invalid={isInvalid}>
                  <div className="flex items-center">
                    <FieldLabel htmlFor={field.name}>Password</FieldLabel>
                    <button
                      className="ml-auto text-sm underline-offset-4 hover:underline cursor-pointer"
                      onClick={enterForgotPasswordMode}
                      type="button"
                    >
                      Forgot your password?
                    </button>
                  </div>
                  <Input
                    autoComplete="current-password"
                    aria-invalid={isInvalid}
                    id={field.name}
                    name={field.name}
                    onBlur={field.handleBlur}
                    onChange={event => field.handleChange(event.target.value)}
                    type="password"
                    value={field.state.value}
                  />
                  {isInvalid ? (
                    <FieldError
                      errors={toFieldErrors(field.state.meta.errors)}
                    />
                  ) : null}
                </Field>
              );
            }}
          />
        ) : null}
      </FieldGroup>

      {showVerificationNotice && !isForgotPasswordMode ? (
        <div className="flex items-start gap-3 rounded-xl border border-emerald-500/25 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-50">
          <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-300">
            <HugeiconsIcon
              aria-hidden="true"
              className="size-4"
              icon={InformationCircleIcon}
              strokeWidth={2}
            />
          </div>
          <div className="space-y-1">
            <p className="font-medium text-emerald-800 dark:text-emerald-100">
              Verify your email
            </p>
            <p className="text-emerald-700/90 dark:text-emerald-50/85">
              Use the link in the email to verify your address.
            </p>
          </div>
        </div>
      ) : null}

      {showPasswordResetNotice && !isForgotPasswordMode ? (
        <p className="text-sm text-muted-foreground">
          Password updated. You can now sign in with your new password.
        </p>
      ) : null}

      {mutation.error && !isForgotPasswordMode ? (
        <p className="text-sm text-destructive">{mutation.error.message}</p>
      ) : null}

      {isEmailNotVerifiedError && !isForgotPasswordMode ? (
        <div className="space-y-2">
          <Button
            className="w-full"
            disabled={resendMutation.isPending || cooldownSeconds > 0}
            onClick={() => {
              void handleResendVerification();
            }}
            type="button"
            variant="outline"
          >
            {resendMutation.isPending
              ? "Sending verification..."
              : cooldownSeconds > 0
                ? `Resend available in ${cooldownSeconds}s`
                : "Resend verification email"}
          </Button>
          {resendFeedback ? (
            <p className="text-sm text-muted-foreground">{resendFeedback}</p>
          ) : null}
          {resendError ? (
            <p className="text-sm text-destructive">{resendError}</p>
          ) : null}
        </div>
      ) : null}

      {isForgotPasswordMode ? (
        <div className="space-y-2">
          {forgotPasswordFeedback ? (
            <p className="text-sm text-muted-foreground">
              {forgotPasswordFeedback}
            </p>
          ) : null}
          {forgotPasswordError ? (
            <p className="text-sm text-destructive">{forgotPasswordError}</p>
          ) : null}
        </div>
      ) : null}

      <div className="space-y-2">
        <TurnstileWidget
          action={isForgotPasswordMode ? "request-password-reset" : "sign-in"}
          onTokenChange={token => {
            setCaptchaToken(token);
            if (token) {
              setCaptchaError(null);
            }
          }}
          ref={turnstileRef}
          siteKey={siteKey}
        />
        {captchaError ? (
          <p className="text-sm text-destructive">{captchaError}</p>
        ) : null}
      </div>

      <Button
        className="w-full cursor-pointer"
        disabled={
          mutation.isPending ||
          googleMutation.isPending ||
          forgotPasswordMutation.isPending ||
          !siteKey ||
          !captchaToken
        }
        type="submit"
      >
        {isForgotPasswordMode
          ? forgotPasswordMutation.isPending
            ? "Sending reset link..."
            : "Send reset link"
          : mutation.isPending
            ? "Signing in..."
            : "Sign in"}
      </Button>

      {isForgotPasswordMode ? (
        <Button
          className="cursor-pointer"
          onBlur={() => backToSignInIconRef.current?.stopAnimation()}
          onClick={leaveForgotPasswordMode}
          onFocus={() => backToSignInIconRef.current?.startAnimation()}
          onMouseEnter={() => backToSignInIconRef.current?.startAnimation()}
          onMouseLeave={() => backToSignInIconRef.current?.stopAnimation()}
          type="button"
          variant="ghost"
        >
          <ArrowLeftIcon ref={backToSignInIconRef} size={16} />
          Back to sign in
        </Button>
      ) : null}
    </form>
  );
};
