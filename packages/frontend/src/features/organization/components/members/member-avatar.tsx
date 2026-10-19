import * as React from "react";
import BoringAvatar from "boring-avatars";
import { useTheme } from "@/components/theme-provider";
import { getAvatarColors } from "@/lib/avatar-colors";

type MemberAvatarProps = {
  seed: string;
  imageUrl?: string | null;
  name?: string;
};

export const MemberAvatar = ({
  seed,
  imageUrl,
  name = "Member avatar",
}: MemberAvatarProps) => {
  const { theme } = useTheme();
  const [failedImageUrl, setFailedImageUrl] = React.useState<string | null>(
    null
  );
  const prefersDark =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
  const resolvedTheme =
    theme === "system" ? (prefersDark ? "dark" : "light") : theme;
  const avatarColors = React.useMemo(
    () => getAvatarColors(seed, resolvedTheme),
    [seed, resolvedTheme]
  );

  return (
    <div className="h-[30px] w-[30px] shrink-0 overflow-hidden rounded-md border border-border/70 leading-none [&>svg]:block! [&>svg]:size-full!">
      {imageUrl && failedImageUrl !== imageUrl ? (
        <img
          src={imageUrl}
          alt={name}
          className="block size-full object-cover"
          loading="lazy"
          onError={() => setFailedImageUrl(imageUrl ?? null)}
        />
      ) : (
        <BoringAvatar
          size="100%"
          name={seed}
          variant="beam"
          colors={avatarColors}
          className="block! size-full!"
          square
        />
      )}
    </div>
  );
};
