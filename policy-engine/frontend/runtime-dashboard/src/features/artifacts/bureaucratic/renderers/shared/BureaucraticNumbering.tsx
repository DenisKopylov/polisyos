type BureaucraticNumberingProps = {
  number?: string | null;
};

export function BureaucraticNumbering({ number }: BureaucraticNumberingProps) {
  if (!number) {
    return null;
  }
  return (
    <span className="mr-2 font-semibold text-black" aria-hidden="true">
      {number}
    </span>
  );
}
