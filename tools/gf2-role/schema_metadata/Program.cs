using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.PortableExecutable;
using System.Text.Json;
using var stream=File.OpenRead(args[0]); using var pe=new PEReader(stream); var md=pe.GetMetadataReader();
var needles=args.Skip(1).ToArray();var constantsOnly=needles.Contains("--constants");var neighbors=needles.Contains("--neighbors");
var selected=new HashSet<int>();if(neighbors)foreach(var th in md.TypeDefinitions){var tn=md.GetString(md.GetTypeDefinition(th).Name);if(needles.Contains(tn))for(int delta=-2;delta<=2;delta++)selected.Add(MetadataTokens.GetToken(th)+delta);}
foreach(var h in md.TypeDefinitions) {
 var t=md.GetTypeDefinition(h);var name=md.GetString(t.Name);if(!constantsOnly&&!(neighbors?selected.Contains(MetadataTokens.GetToken(h)):needles.Any(n=>name.Contains(n,StringComparison.OrdinalIgnoreCase))))continue;
 var fields=t.GetFields().Select(fh=>{var f=md.GetFieldDefinition(fh);var ch=f.GetDefaultValue();object val=null;if(!ch.IsNil){var c=md.GetConstant(ch);var b=md.GetBlobReader(c.Value);val=c.TypeCode==ConstantTypeCode.Int32?b.ReadInt32():Convert.ToHexString(md.GetBlobBytes(c.Value));}return new{name=md.GetString(f.Name),token=MetadataTokens.GetToken(fh),constant=val,signature=Convert.ToHexString(md.GetBlobBytes(f.Signature))};}).ToArray();
 if(constantsOnly&&!fields.Any(f=>f.constant!=null))continue;
 var methods=t.GetMethods().Where(_=>!constantsOnly).Select(mh=>{var m=md.GetMethodDefinition(mh);byte[] il=m.RelativeVirtualAddress==0?Array.Empty<byte>():pe.GetMethodBody(m.RelativeVirtualAddress).GetILBytes();return new{name=md.GetString(m.Name),token=MetadataTokens.GetToken(mh),rva=m.RelativeVirtualAddress,ilLength=il.Length,il=(md.GetString(m.Name)==".cctor"||name.EndsWith("Reflection"))?Convert.ToHexString(il):null};}).ToArray();
 var props=t.GetProperties().Select(ph=>{var p=md.GetPropertyDefinition(ph);return new{name=md.GetString(p.Name),signature=Convert.ToHexString(md.GetBlobBytes(p.Signature))};}).ToArray();
 Console.WriteLine(JsonSerializer.Serialize(new{type=md.GetString(t.Namespace)+"."+name,token=MetadataTokens.GetToken(h),fields,methods,props}));
}
