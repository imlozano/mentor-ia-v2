import Image from "next/image";

import { cn } from "@/lib/utils";

type AppLogoProps = {
  className?: string;
  size?: number;
  priority?: boolean;
};

export function AppLogo({
  className,
  size = 32,
  priority = false,
}: AppLogoProps) {
  return (
    <Image
      src="/logo.png"
      alt="Mentor IA"
      width={size}
      height={size}
      className={cn("shrink-0 object-contain drop-shadow-sm", className)}
      priority={priority}
    />
  );
}
