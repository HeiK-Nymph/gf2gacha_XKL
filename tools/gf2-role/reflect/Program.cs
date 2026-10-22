using System.Reflection;
using System.Text;

// Dump reflection metadata from the game's StaticTable assembly.
// Read-only: the assembly is loaded for inspection only.

if (args.Length < 2)
{
    Console.Error.WriteLine("usage: reflect <assembly> <name-substring> [more substrings...]");
    return 2;
}

var path = args[0];
var needles = args.Skip(1).ToArray();
var assembly = Assembly.LoadFile(Path.GetFullPath(path));
Console.WriteLine($"assembly {assembly.GetName().Name} {assembly.GetName().Version}");

static string Describe(object value)
{
    if (value is null) return "<null>";
    var text = value.ToString() ?? string.Empty;
    return text.Length > 200 ? text[..200] + "..." : text;
}

var types = assembly.GetTypes();
foreach (var needle in needles)
{
    Console.WriteLine($"\n===== {needle} =====");
    var matched = types.Where(t => (t.FullName ?? t.Name).Contains(needle, StringComparison.OrdinalIgnoreCase)).ToList();
    foreach (var type in matched.Take(8))
    {
        Console.WriteLine($"TYPE {type.FullName}");
        foreach (var field in type.GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance).Take(80))
        {
            Console.WriteLine($"  field {field.FieldType.Name} {field.Name}");
        }
        foreach (var prop in type.GetProperties(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance).Take(40))
        {
            Console.WriteLine($"  prop  {prop.PropertyType.Name} {prop.Name}");
        }
        foreach (var staticField in type.GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static))
        {
            if (staticField.Name.Contains("descriptor", StringComparison.OrdinalIgnoreCase))
            {
                try
                {
                    Console.WriteLine($"  static {staticField.Name} = {Describe(staticField.GetValue(null))}");
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"  static {staticField.Name} threw {ex.GetType().Name}");
                }
            }
        }
    }
}

// Generic key/value dump: every reflection type whose name matches the needle,
// printing constructor field names when available.
Console.WriteLine("\n===== reflection types containing 'GunWeapon' or 'Property' =====");
foreach (var type in types.Where(t => t.Name.EndsWith("Reflection")).OrderBy(t => t.Name))
{
    if (!type.Name.Contains("GunWeapon") && !type.Name.Contains("Property")) continue;
    Console.WriteLine(type.Name);
}
return 0;
