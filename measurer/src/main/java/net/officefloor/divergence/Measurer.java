package net.officefloor.divergence;

import java.io.BufferedWriter;
import java.io.IOException;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.jar.Manifest;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.GZIPOutputStream;

import com.github.javaparser.JavaParser;
import com.github.javaparser.JavaToken;
import com.github.javaparser.ParseResult;
import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.ParserConfiguration.LanguageLevel;
import com.github.javaparser.Range;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.Modifier;
import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.NodeList;
import com.github.javaparser.ast.body.AnnotationDeclaration;
import com.github.javaparser.ast.body.BodyDeclaration;
import com.github.javaparser.ast.body.CallableDeclaration;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.CompactConstructorDeclaration;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.body.EnumDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.TypeDeclaration;
import com.github.javaparser.ast.expr.BinaryExpr;
import com.github.javaparser.ast.expr.ConditionalExpr;
import com.github.javaparser.ast.expr.EnclosedExpr;
import com.github.javaparser.ast.expr.Expression;
import com.github.javaparser.ast.expr.LambdaExpr;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.expr.ObjectCreationExpr;
import com.github.javaparser.ast.expr.SimpleName;
import com.github.javaparser.ast.expr.SwitchExpr;
import com.github.javaparser.ast.nodeTypes.NodeWithModifiers;
import com.github.javaparser.ast.stmt.BreakStmt;
import com.github.javaparser.ast.stmt.CatchClause;
import com.github.javaparser.ast.stmt.ContinueStmt;
import com.github.javaparser.ast.stmt.DoStmt;
import com.github.javaparser.ast.stmt.ExplicitConstructorInvocationStmt;
import com.github.javaparser.ast.stmt.ForEachStmt;
import com.github.javaparser.ast.stmt.ForStmt;
import com.github.javaparser.ast.stmt.IfStmt;
import com.github.javaparser.ast.stmt.ReturnStmt;
import com.github.javaparser.ast.stmt.Statement;
import com.github.javaparser.ast.stmt.SwitchEntry;
import com.github.javaparser.ast.stmt.SwitchStmt;
import com.github.javaparser.ast.stmt.ThrowStmt;
import com.github.javaparser.ast.stmt.WhileStmt;
import com.github.javaparser.resolution.declarations.ResolvedReferenceTypeDeclaration;
import com.github.javaparser.resolution.types.ResolvedType;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.symbolsolver.javaparsermodel.JavaParserFacade;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;

/**
 * Per-method coupling (parameters and calls, each call resolved by the symbol solver) and the
 * study's complexity fields re-implemented on JavaParser's syntax tree, for one checkout.
 *
 * <pre>
 *   java -jar divergence-measurer.jar --root DIR --files LIST --out OUT.json.gz [--budget-seconds N]
 * </pre>
 *
 * LIST holds the analysed {@code .java} files, repo-relative, one per line (the harness's file
 * rule decides them; this measurer decides nothing about scope). The rules, as PLAN.md states them:
 *
 * <ul>
 * <li><b>Units:</b> every method and constructor with a body (compact record constructors
 * included), of top-level, nested, local and anonymous classes. A lambda belongs to its
 * enclosing method. The body of a nested type (an anonymous class body, a local class) belongs
 * to that type's own methods, never to the enclosing method.</li>
 * <li><b>Calls:</b> method calls, constructor calls ({@code new T(...)}, an anonymous class
 * creation included; one that is the expression of a {@code throw} is recorded as its own kind,
 * so the harness can report that share) and explicit {@code this(...)}/{@code super(...)};
 * method references are not calls. Each call records its argument count and how it resolved:
 * to a declaration in an
 * analysed file (internal, with that file), to the JDK, to a repository file that is not
 * analysed, not at all, or not at all although its receiver type is declared in the
 * repository ("should have resolved"). The solver sees the source roots of the analysed files
 * plus the JDK (reflection), with no build and no dependencies.</li>
 * <li><b>Complexity fields</b> (the JavaParser-only result set), over the method's own body:
 * cc, cognitive, nesting, exit_points, tokens, nloc and the Halstead volume, with the token
 * classes of the study's lexical estimator. mi and cyc_density are derived by the harness.</li>
 * </ul>
 *
 * Output: one gzipped JSON document (see {@link #write}). Nothing here reads a label or an
 * outcome.
 */
public final class Measurer {

	/** Call kinds. A {@code new} that is the expression of a {@code throw} is CALL_THROW_NEW. */
	static final int CALL_METHOD = 0, CALL_NEW = 1, CALL_EXPLICIT_CTOR = 2, CALL_THROW_NEW = 3;

	/** Call resolutions. */
	static final int RES_INTERNAL = 0, RES_JDK = 1, RES_REPO_NOT_ANALYSED = 2, RES_UNRESOLVED = 3,
			RES_SHOULD_HAVE = 4, RES_BUDGET = 5;

	/** Words the study's lexical Halstead estimator counts as operators (halstead._KW_OPERATORS). */
	static final Set<String> KW_OPERATORS = Set.of("if", "else", "for", "while", "do", "switch", "case",
			"default", "return", "break", "continue", "goto", "try", "catch", "finally", "throw", "throws", "new",
			"delete", "in", "and", "or", "not");

	/** The language levels tried in order: modern Java first, then Java 8 (for `_` and the like). */
	static final LanguageLevel[] LEVELS = { LanguageLevel.JAVA_21, LanguageLevel.JAVA_8 };

	static final Pattern PACKAGE = Pattern.compile("(?m)^\\s*package\\s+([\\w.]+)\\s*;");

	final Path root;
	final List<String> files;
	final Map<String, Integer> fileIndex = new HashMap<>();
	final long budgetMillis;
	final long started = System.currentTimeMillis();
	boolean budgetExhausted = false;
	int clearCounter = 0;

	Measurer(Path root, List<String> files, long budgetSeconds) {
		this.root = root.toAbsolutePath().normalize();
		this.files = files;
		for (int i = 0; i < files.size(); i++) {
			this.fileIndex.put(files.get(i), i);
		}
		this.budgetMillis = budgetSeconds * 1000L;
	}

	public static void main(String[] args) throws Exception {
		String root = null, list = null, out = null;
		long budget = 3600;
		for (int i = 0; i < args.length; i++) {
			switch (args[i]) {
			case "--root" -> root = args[++i];
			case "--files" -> list = args[++i];
			case "--out" -> out = args[++i];
			case "--budget-seconds" -> budget = Long.parseLong(args[++i]);
			case "--version" -> {
				System.out.println(javaParserVersion());
				return;
			}
			default -> throw new IllegalArgumentException("unknown argument " + args[i]);
			}
		}
		if (root == null || list == null || out == null) {
			System.err.println("usage: --root DIR --files LIST --out OUT.json.gz [--budget-seconds N]");
			System.exit(2);
		}
		List<String> files = new ArrayList<>();
		for (String line : Files.readAllLines(Paths.get(list), StandardCharsets.UTF_8)) {
			if (!line.isBlank()) {
				files.add(line.strip());
			}
		}
		new Measurer(Paths.get(root), files, budget).run(Paths.get(out));
	}

	static String javaParserVersion() {
		try (var in = Measurer.class.getResourceAsStream("/META-INF/MANIFEST.MF")) {
			if (in != null) {
				String v = new Manifest(in).getMainAttributes().getValue("JavaParser-Version");
				if (v != null) {
					return v;
				}
			}
		} catch (IOException e) {
			// fall through
		}
		return "unknown";
	}

	// ------------------------------------------------------------------------------------------
	// the run
	// ------------------------------------------------------------------------------------------

	static final class FileRec {
		String path, pkg, level, problem;
		int types;
		final List<MethodRec> methods = new ArrayList<>();
	}

	static final class MethodRec {
		String name, kind, vis, owner;
		int declLine, nameLine, endLine, params;
		boolean local;
		int cc, cognitive, nesting, exitPoints, tokens, nloc;
		double hvol;
		final List<int[]> calls = new ArrayList<>();
	}

	void run(Path out) throws IOException {
		// the source roots: each analysed file's directory less its package path
		Set<Path> roots = new LinkedHashSet<>();
		Map<String, String> pkgs = new HashMap<>();
		for (String f : files) {
			String pkg = "";
			try {
				Matcher m = PACKAGE.matcher(Files.readString(root.resolve(f), StandardCharsets.UTF_8));
				if (m.find()) {
					pkg = m.group(1);
				}
			} catch (IOException | RuntimeException e) {
				// unreadable as UTF-8: the parser reports it below
			}
			pkgs.put(f, pkg);
			Path dir = root.resolve(f).getParent();
			Path pkgPath = pkg.isEmpty() ? null : Paths.get(pkg.replace('.', '/'));
			if (pkgPath != null && dir.endsWith(pkgPath)) {
				Path r = dir;
				for (int i = 0; i < pkgPath.getNameCount(); i++) {
					r = r.getParent();
				}
				roots.add(r);
			} else {
				roots.add(dir);
			}
		}
		ParserConfiguration solverConfig = new ParserConfiguration().setLanguageLevel(LEVELS[0]);
		CombinedTypeSolver solver = new CombinedTypeSolver(new ReflectionTypeSolver(true));
		for (Path r : roots) {
			solver.add(new JavaParserTypeSolver(r, solverConfig, 5000));
		}
		JavaSymbolSolver symbols = new JavaSymbolSolver(solver);

		List<FileRec> recs = new ArrayList<>();
		for (String f : files) {
			FileRec rec = new FileRec();
			rec.path = f;
			rec.pkg = pkgs.get(f);
			CompilationUnit cu = null;
			for (LanguageLevel level : LEVELS) {
				JavaParser parser = new JavaParser(
						new ParserConfiguration().setLanguageLevel(level).setSymbolResolver(symbols));
				try {
					ParseResult<CompilationUnit> pr = parser.parse(root.resolve(f));
					if (pr.isSuccessful() && pr.getResult().isPresent()) {
						cu = pr.getResult().get();
						rec.level = level.name();
						break;
					}
					rec.problem = pr.getProblems().isEmpty() ? "no result"
							: pr.getProblems().get(0).getVerboseMessage();
				} catch (IOException | RuntimeException | StackOverflowError e) {
					rec.problem = e.getClass().getSimpleName() + ": " + e.getMessage();
				}
			}
			if (cu == null) {
				rec.level = "failed";
			} else {
				rec.problem = null;
				measureFile(cu, rec);
			}
			recs.add(rec);
			if (++clearCounter % 200 == 0) {
				JavaParserFacade.clearInstances(); // bound the solver's memory on large repositories
			}
		}
		write(out, recs, roots);
	}

	void measureFile(CompilationUnit cu, FileRec rec) {
		rec.types = cu.findAll(TypeDeclaration.class).size();
		for (Node n : cu.findAll(Node.class, x -> x instanceof CallableDeclaration
				|| x instanceof CompactConstructorDeclaration)) {
			if (n instanceof MethodDeclaration md && md.getBody().isEmpty()) {
				continue; // abstract, interface or native: no body, not a unit
			}
			MethodRec m = new MethodRec();
			measureCallable(n, rec.path, m);
			rec.methods.add(m);
		}
	}

	// ------------------------------------------------------------------------------------------
	// one callable
	// ------------------------------------------------------------------------------------------

	/** The nearest declaring scope of a member: a type declaration or an anonymous class creation. */
	static Node owner(Node member) {
		Node p = member.getParentNode().orElse(null);
		while (p != null) {
			if (p instanceof TypeDeclaration) {
				return p;
			}
			if (p instanceof ObjectCreationExpr oce && oce.getAnonymousClassBody().isPresent()) {
				return p;
			}
			p = p.getParentNode().orElse(null);
		}
		return null;
	}

	/** Whether a member is declared in an anonymous or local class (not a member of the file's types). */
	static boolean isLocal(Node member) {
		Node o = owner(member);
		while (o != null) {
			if (o instanceof ObjectCreationExpr) {
				return true;
			}
			if (o instanceof ClassOrInterfaceDeclaration cid && cid.isLocalClassDeclaration()) {
				return true;
			}
			if (o instanceof TypeDeclaration<?> td && td.findAncestor(CallableDeclaration.class).isPresent()) {
				return true; // a local record or enum
			}
			o = owner(o);
		}
		return false;
	}

	static String visibility(Node member) {
		if (member instanceof NodeWithModifiers<?> nm) {
			NodeList<Modifier> mods = nm.getModifiers();
			for (Modifier mod : mods) {
				switch (mod.getKeyword()) {
				case PUBLIC:
					return "public";
				case PROTECTED:
					return "protected";
				case PRIVATE:
					return "private";
				default:
					break;
				}
			}
		}
		Node o = owner(member);
		if (o instanceof ClassOrInterfaceDeclaration cid && cid.isInterface() && member instanceof MethodDeclaration) {
			return "public"; // interface methods are implicitly public
		}
		if (o instanceof AnnotationDeclaration) {
			return "public";
		}
		if (o instanceof EnumDeclaration && member instanceof ConstructorDeclaration) {
			return "private"; // enum constructors are implicitly private
		}
		return "package";
	}

	/** Whether a child node belongs to a nested type's own members rather than to the enclosing body. */
	static boolean isNestedTypePart(Node parent, Node child) {
		if (child instanceof TypeDeclaration) {
			return true; // a local class, record or enum
		}
		return parent instanceof ObjectCreationExpr && child instanceof BodyDeclaration;
	}

	/** Every node of a callable's own body, depth first (nested type members excluded). */
	static void ownNodes(Node n, List<Node> out) {
		out.add(n);
		for (Node c : n.getChildNodes()) {
			if (!isNestedTypePart(n, c)) {
				ownNodes(c, out);
			}
		}
	}

	/** The ranges of nested type members inside a callable, whose tokens are not the callable's. */
	static void nestedRanges(Node n, List<Range> out) {
		for (Node c : n.getChildNodes()) {
			if (isNestedTypePart(n, c)) {
				c.getRange().ifPresent(out::add);
			} else {
				nestedRanges(c, out);
			}
		}
	}

	void measureCallable(Node decl, String file, MethodRec m) {
		SimpleName name;
		NodeList<?> params;
		Node body;
		if (decl instanceof MethodDeclaration md) {
			name = md.getName();
			params = md.getParameters();
			body = md.getBody().get();
			m.kind = "method";
		} else if (decl instanceof ConstructorDeclaration cd) {
			name = cd.getName();
			params = cd.getParameters();
			body = cd.getBody();
			m.kind = "ctor";
		} else {
			CompactConstructorDeclaration ccd = (CompactConstructorDeclaration) decl;
			name = ccd.getName();
			params = new NodeList<>(); // a compact constructor declares no parameter list
			body = ccd.getBody();
			m.kind = "ctor";
		}
		m.name = name.asString();
		m.params = params.size(); // a varargs parameter is one parameter
		m.declLine = decl.getBegin().map(p -> p.line).orElse(0);
		m.nameLine = name.getBegin().map(p -> p.line).orElse(m.declLine);
		m.endLine = decl.getEnd().map(p -> p.line).orElse(m.declLine);
		m.vis = visibility(decl);
		m.local = isLocal(decl);
		Node o = owner(decl);
		m.owner = o instanceof TypeDeclaration<?> td ? td.getNameAsString() : "(anonymous)";

		List<Node> own = new ArrayList<>();
		ownNodes(body, own);
		// parameters and the signature are not branching code; the counts below read the body
		int cc = 1, exits = 0;
		for (Node n : own) {
			if (n instanceof IfStmt || n instanceof ForStmt || n instanceof ForEachStmt || n instanceof WhileStmt
					|| n instanceof DoStmt || n instanceof CatchClause || n instanceof ConditionalExpr) {
				cc++;
			} else if (n instanceof BinaryExpr be && (be.getOperator() == BinaryExpr.Operator.AND
					|| be.getOperator() == BinaryExpr.Operator.OR)) {
				cc++;
			} else if (n instanceof SwitchEntry se && !se.getLabels().isEmpty()) {
				cc++; // one `case` keyword per entry, as lizard counts it; `default` adds nothing
			} else if (n instanceof ReturnStmt || n instanceof ThrowStmt) {
				exits++;
			}
			if (n instanceof MethodCallExpr mce) {
				m.calls.add(call(mce, mce.getArguments().size(), CALL_METHOD));
			} else if (n instanceof ObjectCreationExpr oce) {
				boolean thrown = oce.getParentNode().map(p -> p instanceof ThrowStmt).orElse(false);
				m.calls.add(call(oce, oce.getArguments().size(), thrown ? CALL_THROW_NEW : CALL_NEW));
			} else if (n instanceof ExplicitConstructorInvocationStmt ecis) {
				m.calls.add(call(ecis, ecis.getArguments().size(), CALL_EXPLICIT_CTOR));
			}
		}
		m.cc = cc;
		m.exitPoints = exits;
		Cognitive cog = new Cognitive();
		cog.visit(body, 0);
		m.cognitive = cog.score;
		m.nesting = cog.maxNesting;
		tokens(decl, name, m);
	}

	/** tokens, nloc and the Halstead volume over the tokens from the name to the end of the body. */
	static void tokens(Node decl, SimpleName name, MethodRec m) {
		List<Range> skip = new ArrayList<>();
		nestedRanges(decl, skip);
		Optional<JavaToken> first = name.getTokenRange().map(tr -> tr.getBegin());
		Optional<JavaToken> last = decl.getTokenRange().map(tr -> tr.getEnd());
		if (first.isEmpty() || last.isEmpty()) {
			return;
		}
		Map<String, Integer> operators = new HashMap<>(), operands = new HashMap<>();
		Set<Integer> lines = new HashSet<>();
		int count = 0;
		JavaToken t = first.get();
		while (t != null) {
			JavaToken tok = t;
			JavaToken.Category cat = tok.getCategory();
			boolean code = !(cat.isWhitespaceOrComment());
			if (code && tok.getRange().isPresent()) {
				Range r = tok.getRange().get();
				boolean nested = false;
				for (Range s : skip) {
					if (s.contains(r)) {
						nested = true;
						break;
					}
				}
				if (!nested) {
					count++;
					lines.add(r.begin.line);
					String text = tok.getText();
					if (cat.isOperator() || cat.isSeparator()
							|| (cat.isKeyword() && KW_OPERATORS.contains(text))) {
						operators.merge(text, 1, Integer::sum);
					} else {
						operands.merge(text, 1, Integer::sum);
					}
				}
			}
			if (tok == last.get()) {
				break;
			}
			t = tok.getNextToken().orElse(null);
		}
		m.tokens = count;
		m.nloc = lines.size();
		int n1 = operators.size(), n2 = operands.size();
		int bigN = 0;
		for (int v : operators.values()) {
			bigN += v;
		}
		for (int v : operands.values()) {
			bigN += v;
		}
		int vocab = n1 + n2;
		m.hvol = (vocab < 2 || bigN == 0) ? 0.0 : Math.round(bigN * (Math.log(vocab) / Math.log(2)) * 100.0) / 100.0;
	}

	/** Campbell's cognitive complexity and the maximum nesting it reaches, over one body. */
	static final class Cognitive {
		int score = 0, maxNesting = 0;

		void nest(int level) {
			maxNesting = Math.max(maxNesting, level);
		}

		void visit(Node n, int nesting) {
			if (n instanceof IfStmt s) {
				ifStmt(s, nesting, false);
			} else if (n instanceof ForStmt || n instanceof ForEachStmt || n instanceof WhileStmt
					|| n instanceof DoStmt) {
				score += 1 + nesting;
				nest(nesting + 1);
				Statement body = n instanceof ForStmt f ? f.getBody()
						: n instanceof ForEachStmt fe ? fe.getBody()
								: n instanceof WhileStmt w ? w.getBody() : ((DoStmt) n).getBody();
				children(n, nesting, body, nesting + 1);
			} else if (n instanceof SwitchStmt || n instanceof SwitchExpr) {
				score += 1 + nesting;
				nest(nesting + 1);
				for (Node c : n.getChildNodes()) {
					visit(c, c instanceof SwitchEntry ? nesting + 1 : nesting);
				}
			} else if (n instanceof CatchClause cc) {
				score += 1 + nesting;
				nest(nesting + 1);
				children(n, nesting, cc.getBody(), nesting + 1);
			} else if (n instanceof ConditionalExpr ce) {
				score += 1 + nesting;
				nest(nesting + 1);
				visit(ce.getCondition(), nesting);
				visit(ce.getThenExpr(), nesting + 1);
				visit(ce.getElseExpr(), nesting + 1);
			} else if (n instanceof LambdaExpr le) {
				nest(nesting + 1); // a lambda body nests, and scores nothing itself
				for (Node c : le.getChildNodes()) {
					visit(c, nesting + 1);
				}
			} else if (n instanceof BreakStmt b && b.getLabel().isPresent()) {
				score += 1;
			} else if (n instanceof ContinueStmt c && c.getLabel().isPresent()) {
				score += 1;
			} else if (n instanceof BinaryExpr be && logical(be)) {
				// one +1 per run of like operators over the whole logical expression
				List<BinaryExpr.Operator> ops = new ArrayList<>();
				List<Expression> leaves = new ArrayList<>();
				flatten(be, ops, leaves);
				BinaryExpr.Operator prev = null;
				for (BinaryExpr.Operator op : ops) {
					if (op != prev) {
						score++;
					}
					prev = op;
				}
				for (Expression leaf : leaves) {
					visit(leaf, nesting);
				}
			} else {
				for (Node c : n.getChildNodes()) {
					if (!isNestedTypePart(n, c)) {
						visit(c, nesting);
					}
				}
			}
		}

		void children(Node n, int nesting, Node body, int bodyNesting) {
			for (Node c : n.getChildNodes()) {
				visit(c, c == body ? bodyNesting : nesting);
			}
		}

		void ifStmt(IfStmt s, int nesting, boolean elseIf) {
			score += elseIf ? 1 : 1 + nesting;
			nest(nesting + 1);
			visit(s.getCondition(), nesting);
			visit(s.getThenStmt(), nesting + 1);
			if (s.getElseStmt().isPresent()) {
				Statement e = s.getElseStmt().get();
				if (e instanceof IfStmt elif) {
					ifStmt(elif, nesting, true);
				} else {
					score += 1;
					visit(e, nesting + 1);
				}
			}
		}

		static boolean logical(Node n) {
			return n instanceof BinaryExpr be
					&& (be.getOperator() == BinaryExpr.Operator.AND || be.getOperator() == BinaryExpr.Operator.OR);
		}

		static void flatten(Expression e, List<BinaryExpr.Operator> ops, List<Expression> leaves) {
			Expression x = e;
			while (x instanceof EnclosedExpr ee && logical(ee.getInner())) {
				x = ee.getInner();
			}
			if (x instanceof BinaryExpr be && logical(be)) {
				flatten(be.getLeft(), ops, leaves);
				ops.add(be.getOperator());
				flatten(be.getRight(), ops, leaves);
			} else {
				leaves.add(x);
			}
		}
	}

	// ------------------------------------------------------------------------------------------
	// call resolution
	// ------------------------------------------------------------------------------------------

	/** [arguments, kind, resolution, target file index or -1]. */
	int[] call(Node n, int args, int kind) {
		if (budgetMillis > 0 && System.currentTimeMillis() - started > budgetMillis) {
			budgetExhausted = true;
			return new int[] { args, kind, RES_BUDGET, -1 };
		}
		ResolvedReferenceTypeDeclaration declaring = null;
		try {
			if (n instanceof MethodCallExpr mce) {
				declaring = mce.resolve().declaringType();
			} else if (n instanceof ObjectCreationExpr oce) {
				declaring = oce.resolve().declaringType();
			} else {
				declaring = ((ExplicitConstructorInvocationStmt) n).resolve().declaringType();
			}
		} catch (Throwable e) {
			if (e instanceof OutOfMemoryError oom) {
				throw oom;
			}
			return new int[] { args, kind, shouldHave(n) ? RES_SHOULD_HAVE : RES_UNRESOLVED, -1 };
		}
		Optional<String> file = fileOf(declaring);
		if (file.isEmpty()) {
			return new int[] { args, kind, RES_JDK, -1 };
		}
		Integer idx = fileIndex.get(file.get());
		return idx == null ? new int[] { args, kind, RES_REPO_NOT_ANALYSED, -1 }
				: new int[] { args, kind, RES_INTERNAL, idx };
	}

	/** The repo-relative file declaring a resolved type, or empty for a type with no source (the JDK). */
	Optional<String> fileOf(ResolvedReferenceTypeDeclaration t) {
		try {
			Optional<Node> ast = t.toAst();
			if (ast.isEmpty()) {
				return Optional.empty();
			}
			Optional<Path> p = ast.get().findCompilationUnit().flatMap(CompilationUnit::getStorage)
					.map(s -> s.getPath());
			if (p.isEmpty()) {
				return Optional.of("?");
			}
			Path abs = p.get().toAbsolutePath().normalize();
			if (!abs.startsWith(root)) {
				return Optional.of("?");
			}
			return Optional.of(root.relativize(abs).toString().replace('\\', '/'));
		} catch (Throwable e) {
			if (e instanceof OutOfMemoryError oom) {
				throw oom;
			}
			return Optional.of("?");
		}
	}

	/**
	 * Whether an unresolved call's receiver type is declared in the repository: an explicit
	 * receiver whose type resolves to a repository declaration, or an implicit {@code this} (or
	 * a constructor of a type) whose declaration and every ancestor resolve, so the method should
	 * have been found.
	 */
	boolean shouldHave(Node n) {
		try {
			if (n instanceof MethodCallExpr mce && mce.getScope().isPresent()) {
				ResolvedType t = mce.getScope().get().calculateResolvedType();
				return t.isReferenceType() && t.asReferenceType().getTypeDeclaration()
						.map(d -> fileOf(d).filter(f -> !f.equals("?")).isPresent()).orElse(false);
			}
			if (n instanceof ObjectCreationExpr oce) {
				ResolvedType t = oce.getType().resolve();
				return t.isReferenceType() && t.asReferenceType().getTypeDeclaration()
						.map(d -> fileOf(d).filter(f -> !f.equals("?")).isPresent()).orElse(false);
			}
			Optional<TypeDeclaration> td = n.findAncestor(TypeDeclaration.class);
			if (td.isEmpty()) {
				return false;
			}
			ResolvedReferenceTypeDeclaration d = td.get().resolve();
			d.getAllAncestors(); // throws when an ancestor is a type the solver cannot see
			return true;
		} catch (Throwable e) {
			if (e instanceof OutOfMemoryError oom) {
				throw oom;
			}
			return false;
		}
	}

	// ------------------------------------------------------------------------------------------
	// output
	// ------------------------------------------------------------------------------------------

	/**
	 * Writes {"javaparser", "levels", "roots", "seconds", "budget_seconds", "budget_exhausted",
	 * "files": [{"path", "package", "level", "problem", "types", "methods": [{"name", "kind",
	 * "owner", "vis", "local", "decl_line", "name_line", "end_line", "params", "cc", "cognitive",
	 * "nesting", "exit_points", "tokens", "nloc", "hvol", "calls": [[args, kind, res, file]]}]}]}.
	 */
	void write(Path out, List<FileRec> recs, Set<Path> roots) throws IOException {
		Path tmp = out.resolveSibling(out.getFileName() + ".part");
		try (Writer w = new BufferedWriter(
				new OutputStreamWriter(new GZIPOutputStream(Files.newOutputStream(tmp)), StandardCharsets.UTF_8))) {
			w.write("{\"javaparser\":");
			str(w, javaParserVersion());
			w.write(",\"levels\":[");
			for (int i = 0; i < LEVELS.length; i++) {
				w.write((i > 0 ? "," : ""));
				str(w, LEVELS[i].name());
			}
			w.write("],\"roots\":[");
			int i = 0;
			for (Path r : roots) {
				w.write(i++ > 0 ? "," : "");
				str(w, root.relativize(r).toString().replace('\\', '/'));
			}
			w.write("],\"seconds\":" + (System.currentTimeMillis() - started) / 1000.0);
			w.write(",\"budget_seconds\":" + budgetMillis / 1000);
			w.write(",\"budget_exhausted\":" + budgetExhausted);
			w.write(",\"files\":[");
			for (int f = 0; f < recs.size(); f++) {
				FileRec fr = recs.get(f);
				w.write(f > 0 ? ",\n" : "\n");
				w.write("{\"path\":");
				str(w, fr.path);
				w.write(",\"package\":");
				str(w, fr.pkg);
				w.write(",\"level\":");
				str(w, fr.level);
				w.write(",\"problem\":");
				str(w, fr.problem);
				w.write(",\"types\":" + fr.types + ",\"methods\":[");
				for (int k = 0; k < fr.methods.size(); k++) {
					MethodRec m = fr.methods.get(k);
					w.write(k > 0 ? "," : "");
					w.write("{\"name\":");
					str(w, m.name);
					w.write(",\"kind\":");
					str(w, m.kind);
					w.write(",\"owner\":");
					str(w, m.owner);
					w.write(",\"vis\":");
					str(w, m.vis);
					w.write(",\"local\":" + m.local + ",\"decl_line\":" + m.declLine + ",\"name_line\":" + m.nameLine
							+ ",\"end_line\":" + m.endLine + ",\"params\":" + m.params + ",\"cc\":" + m.cc
							+ ",\"cognitive\":" + m.cognitive + ",\"nesting\":" + m.nesting + ",\"exit_points\":"
							+ m.exitPoints + ",\"tokens\":" + m.tokens + ",\"nloc\":" + m.nloc + ",\"hvol\":" + m.hvol
							+ ",\"calls\":[");
					for (int c = 0; c < m.calls.size(); c++) {
						int[] cl = m.calls.get(c);
						w.write((c > 0 ? "," : "") + "[" + cl[0] + "," + cl[1] + "," + cl[2] + "," + cl[3] + "]");
					}
					w.write("]}");
				}
				w.write("]}");
			}
			w.write("]}\n");
		}
		Files.move(tmp, out, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
	}

	static void str(Writer w, String s) throws IOException {
		if (s == null) {
			w.write("null");
			return;
		}
		StringBuilder b = new StringBuilder(s.length() + 2).append('"');
		for (int i = 0; i < s.length(); i++) {
			char c = s.charAt(i);
			switch (c) {
			case '"' -> b.append("\\\"");
			case '\\' -> b.append("\\\\");
			case '\n' -> b.append("\\n");
			case '\r' -> b.append("\\r");
			case '\t' -> b.append("\\t");
			default -> {
				if (c < 0x20) {
					b.append(String.format("\\u%04x", (int) c));
				} else {
					b.append(c);
				}
			}
			}
		}
		w.write(b.append('"').toString());
	}
}
