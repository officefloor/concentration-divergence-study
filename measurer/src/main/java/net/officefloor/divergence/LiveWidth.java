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
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;
import java.util.regex.Pattern;
import java.util.zip.GZIPOutputStream;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParseResult;
import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.ParserConfiguration.LanguageLevel;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.NodeList;
import com.github.javaparser.ast.body.CallableDeclaration;
import com.github.javaparser.ast.body.CompactConstructorDeclaration;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.Parameter;
import com.github.javaparser.ast.body.VariableDeclarator;
import com.github.javaparser.ast.expr.AnnotationExpr;
import com.github.javaparser.ast.expr.ArrayAccessExpr;
import com.github.javaparser.ast.expr.AssignExpr;
import com.github.javaparser.ast.expr.CharLiteralExpr;
import com.github.javaparser.ast.expr.DoubleLiteralExpr;
import com.github.javaparser.ast.expr.Expression;
import com.github.javaparser.ast.expr.FieldAccessExpr;
import com.github.javaparser.ast.expr.IntegerLiteralExpr;
import com.github.javaparser.ast.expr.LambdaExpr;
import com.github.javaparser.ast.expr.LongLiteralExpr;
import com.github.javaparser.ast.expr.NameExpr;
import com.github.javaparser.ast.expr.SimpleName;
import com.github.javaparser.ast.expr.ThisExpr;
import com.github.javaparser.ast.expr.TypePatternExpr;
import com.github.javaparser.ast.expr.UnaryExpr;
import com.github.javaparser.ast.expr.VariableDeclarationExpr;
import com.github.javaparser.ast.stmt.CatchClause;
import com.github.javaparser.ast.stmt.DoStmt;
import com.github.javaparser.ast.stmt.ForEachStmt;
import com.github.javaparser.ast.stmt.ForStmt;
import com.github.javaparser.ast.stmt.Statement;
import com.github.javaparser.ast.stmt.SwitchEntry;
import com.github.javaparser.ast.stmt.TryStmt;
import com.github.javaparser.ast.stmt.WhileStmt;

/**
 * EXPLORATORY, POST HOC (PLAN.md, Amendments, 10: every oracle had been read when this was
 * written). The facts a live-width measure is computed from, per method: every variable the
 * method's own body reads or writes, the lines of its first and last reference, and how often it
 * is assigned. The widths themselves are computed by scripts/livewidth.py, so every variant is
 * read from one pass.
 *
 * <pre>
 *   java -cp divergence-measurer.jar net.officefloor.divergence.LiveWidth --root DIR --files LIST --out OUT.json.gz
 * </pre>
 *
 * The units are exactly the measurer's (every callable with a body, keyed by file, name and name
 * line; a lambda belongs to its enclosing method; the bodies of nested types do not). No symbol
 * solver: names are matched to declarations by lexical scope alone. The rules:
 *
 * <ul>
 * <li><b>Variables:</b> parameters of the callable (PARAM); locals, for and for-each variables,
 * resources, catch and lambda parameters and pattern variables (LOCAL); and fields (FIELD): a
 * {@code this.x}, or a simple name no local declaration in scope matches. A simple name starting
 * with an upper-case letter is taken as a type or a constant and is not a variable; nor is an
 * enum constant as a {@code case} label.</li>
 * <li><b>References:</b> every use of the variable, a write included; a declarator's
 * initializer, a for-each variable and a pattern are references at their own line. A
 * parameter's declaration is not a reference (its signature line is written beside it).</li>
 * <li><b>Definitions</b> ({@code defs}): the value a variable enters with (a parameter's
 * argument, a field's prior state, a catch, lambda, for-each or pattern binding, an
 * initializer), plus every assignment and increment of the name. {@code steps}: the definitions
 * that are steps (an increment or decrement, {@code +=}/{@code -=} of a literal, or any
 * definition in a for statement's update). {@code muts}: writes into the variable's object
 * ({@code a[i] = v}, {@code a.f = v}), which do not rebind it.</li>
 * <li><b>Loops:</b> for each variable, the extent it is live over when control flow is followed
 * this far: a variable declared outside a loop and referenced inside it is live over the whole
 * loop (the back edge), so its range is widened to cover it.</li>
 * </ul>
 */
public final class LiveWidth {

	static final int PARAM = 0, LOCAL = 1, FIELD = 2;

	/** The facts schema, bumped with any change to the rules above. */
	static final int SCHEMA = 1;

	static final Pattern UPPER = Pattern.compile("^[A-Z].*");

	static final class Var {
		final int kind;
		final String name;
		/** The node the declaration is visible in (null for a field). */
		final Node scope;
		/** Where the declaration is, for the declared-before rule (0 for a parameter or field). */
		final int declLine, declCol;
		final List<Node> refs = new ArrayList<>();
		int first = Integer.MAX_VALUE, last = -1, defs, steps, muts;

		Var(int kind, String name, Node scope, Node at, int defs) {
			this.kind = kind;
			this.name = name;
			this.scope = scope;
			this.declLine = at == null ? 0 : at.getBegin().map(p -> p.line).orElse(0);
			this.declCol = at == null ? 0 : at.getBegin().map(p -> p.column).orElse(0);
			this.defs = defs;
		}

		void ref(Node n) {
			int line = line(n);
			refs.add(n);
			first = Math.min(first, line);
			last = Math.max(last, line);
		}
	}

	static final class MethodFacts {
		String name;
		int declLine, nameLine, endLine;
		final TreeSet<Integer> lines = new TreeSet<>();
		final List<Var> vars = new ArrayList<>();
		final List<int[]> loopRanges = new ArrayList<>();
		final Map<Var, int[]> loopExtent = new IdentityHashMap<>();
	}

	static final class FileFacts {
		String path, level, problem;
		final List<MethodFacts> methods = new ArrayList<>();
	}

	public static void main(String[] args) throws Exception {
		String root = null, list = null, out = null;
		for (int i = 0; i < args.length; i++) {
			switch (args[i]) {
			case "--root" -> root = args[++i];
			case "--files" -> list = args[++i];
			case "--out" -> out = args[++i];
			case "--version" -> {
				System.out.println(Measurer.javaParserVersion() + " schema " + SCHEMA);
				return;
			}
			default -> throw new IllegalArgumentException("unknown argument " + args[i]);
			}
		}
		if (root == null || list == null || out == null) {
			System.err.println("usage: --root DIR --files LIST --out OUT.json.gz");
			System.exit(2);
		}
		List<String> files = new ArrayList<>();
		for (String line : Files.readAllLines(Paths.get(list), StandardCharsets.UTF_8)) {
			if (!line.isBlank()) {
				files.add(line.strip());
			}
		}
		long started = System.currentTimeMillis();
		Path base = Paths.get(root).toAbsolutePath().normalize();
		List<FileFacts> recs = new ArrayList<>();
		for (String f : files) {
			recs.add(measureFile(base, f));
		}
		write(Paths.get(out), recs, (System.currentTimeMillis() - started) / 1000.0);
	}

	/** One file, parsed at the measurer's language levels in its order. */
	static FileFacts measureFile(Path base, String f) {
		FileFacts rec = new FileFacts();
		rec.path = f;
		CompilationUnit cu = null;
		for (LanguageLevel level : Measurer.LEVELS) {
			JavaParser parser = new JavaParser(new ParserConfiguration().setLanguageLevel(level));
			try {
				ParseResult<CompilationUnit> pr = parser.parse(base.resolve(f));
				if (pr.isSuccessful() && pr.getResult().isPresent()) {
					cu = pr.getResult().get();
					rec.level = level.name();
					break;
				}
				rec.problem = pr.getProblems().isEmpty() ? "no result" : pr.getProblems().get(0).getVerboseMessage();
			} catch (IOException | RuntimeException | StackOverflowError e) {
				rec.problem = e.getClass().getSimpleName() + ": " + e.getMessage();
			}
		}
		if (cu == null) {
			rec.level = "failed";
			return rec;
		}
		rec.problem = null;
		for (Node n : cu.findAll(Node.class,
				x -> x instanceof CallableDeclaration || x instanceof CompactConstructorDeclaration)) {
			if (n instanceof MethodDeclaration md && md.getBody().isEmpty()) {
				continue; // as the measurer: no body, not a unit
			}
			try {
				rec.methods.add(measureCallable(n));
			} catch (RuntimeException | StackOverflowError e) {
				MethodFacts m = new MethodFacts();
				m.name = "(failed) " + e.getClass().getSimpleName();
				rec.methods.add(m);
			}
		}
		return rec;
	}

	static int line(Node n) {
		return n.getBegin().map(p -> p.line).orElse(0);
	}

	static int col(Node n) {
		return n.getBegin().map(p -> p.column).orElse(0);
	}

	static boolean within(Node ancestor, Node n) {
		return ancestor == n || ancestor.isAncestorOf(n);
	}

	static MethodFacts measureCallable(Node decl) {
		SimpleName name;
		NodeList<Parameter> params;
		Node body;
		if (decl instanceof MethodDeclaration md) {
			name = md.getName();
			params = md.getParameters();
			body = md.getBody().get();
		} else if (decl instanceof ConstructorDeclaration cd) {
			name = cd.getName();
			params = cd.getParameters();
			body = cd.getBody();
		} else {
			CompactConstructorDeclaration ccd = (CompactConstructorDeclaration) decl;
			name = ccd.getName();
			params = new NodeList<>(); // the record components read as fields
			body = ccd.getBody();
		}
		MethodFacts m = new MethodFacts();
		m.name = name.asString();
		m.declLine = line(decl);
		m.nameLine = name.getBegin().map(p -> p.line).orElse(m.declLine);
		m.endLine = decl.getEnd().map(p -> p.line).orElse(m.declLine);

		List<Node> own = new ArrayList<>();
		Measurer.ownNodes(body, own);
		m.lines.add(m.nameLine);
		for (Node n : own) {
			m.lines.add(line(n));
		}

		// declarations, each with the node it is visible in
		List<Var> locals = new ArrayList<>();
		for (Parameter p : params) {
			locals.add(new Var(PARAM, p.getNameAsString(), decl, null, 1));
		}
		for (Node n : own) {
			if (n instanceof VariableDeclarator vd && vd.getParentNode().orElse(null) instanceof VariableDeclarationExpr vde) {
				Node holder = vde.getParentNode().orElse(vde);
				Node scope = holder instanceof ForStmt || holder instanceof ForEachStmt || holder instanceof TryStmt ? holder
						: holder.getParentNode().orElse(holder);
				boolean bound = vd.getInitializer().isPresent() || holder instanceof ForEachStmt;
				Var v = new Var(LOCAL, vd.getNameAsString(), scope, vd.getName(), bound ? 1 : 0);
				if (bound) {
					v.ref(vd.getName());
				}
				locals.add(v);
			} else if (n instanceof Parameter p) {
				Node owner = p.getParentNode().orElse(null);
				if (owner instanceof CatchClause || owner instanceof LambdaExpr) {
					locals.add(new Var(LOCAL, p.getNameAsString(), owner, p.getName(), 1));
				}
			} else if (n instanceof TypePatternExpr tp) {
				Var v = new Var(LOCAL, tp.getNameAsString(), patternScope(tp), tp.getName(), 1);
				v.ref(tp.getName());
				locals.add(v);
			}
		}

		// references, matched to the innermost declaration in scope
		Map<String, Var> fields = new LinkedHashMap<>();
		for (Node n : own) {
			Var v = null;
			if (n instanceof NameExpr ne) {
				if (excluded(ne)) {
					continue;
				}
				v = resolve(ne, locals);
				if (v == null) {
					v = fields.computeIfAbsent(ne.getNameAsString(), k -> new Var(FIELD, k, null, null, 1));
				}
				v.ref(ne);
			} else if (n instanceof FieldAccessExpr fa && fa.getScope() instanceof ThisExpr) {
				v = fields.computeIfAbsent(fa.getNameAsString(), k -> new Var(FIELD, k, null, null, 1));
				v.ref(fa);
			}
		}

		// definitions
		for (Node n : own) {
			Expression target = null;
			boolean step = false;
			if (n instanceof AssignExpr ae) {
				target = ae.getTarget();
				step = (ae.getOperator() == AssignExpr.Operator.PLUS || ae.getOperator() == AssignExpr.Operator.MINUS)
						&& isLiteral(ae.getValue());
			} else if (n instanceof UnaryExpr ue && (ue.getOperator() == UnaryExpr.Operator.PREFIX_INCREMENT
					|| ue.getOperator() == UnaryExpr.Operator.PREFIX_DECREMENT
					|| ue.getOperator() == UnaryExpr.Operator.POSTFIX_INCREMENT
					|| ue.getOperator() == UnaryExpr.Operator.POSTFIX_DECREMENT)) {
				target = ue.getExpression();
				step = true;
			}
			if (target == null) {
				continue;
			}
			boolean inUpdate = n.findAncestor(ForStmt.class)
					.map(fs -> fs.getUpdate().stream().anyMatch(u -> within(u, n))).orElse(false);
			Var rebound = varOf(target, locals, fields);
			if (rebound != null) {
				rebound.defs++;
				if (step || inUpdate) {
					rebound.steps++;
				}
				continue;
			}
			Expression base = target;
			while (base instanceof ArrayAccessExpr || base instanceof FieldAccessExpr) {
				base = base instanceof ArrayAccessExpr aa ? aa.getName() : ((FieldAccessExpr) base).getScope();
				Var into = varOf(base, locals, fields);
				if (into != null) {
					into.muts++;
					break;
				}
			}
		}

		for (Var v : locals) {
			if (!v.refs.isEmpty()) {
				m.vars.add(v);
			}
		}
		m.vars.addAll(fields.values());

		// loops: a variable declared outside a loop and referenced inside it is live over all of it
		List<Node> loops = new ArrayList<>();
		for (Node n : own) {
			if (n instanceof ForStmt || n instanceof ForEachStmt || n instanceof WhileStmt || n instanceof DoStmt) {
				loops.add(n);
				m.loopRanges.add(new int[] { line(n), n.getEnd().map(p -> p.line).orElse(line(n)) });
			}
		}
		for (Var v : m.vars) {
			int lo = v.first, hi = v.last;
			for (Node loop : loops) {
				if (v.scope != null && within(loop, v.scope)) {
					continue; // declared in the loop: a fresh variable each iteration
				}
				boolean inside = false;
				for (Node r : v.refs) {
					if (loop.isAncestorOf(r)) {
						inside = true;
						break;
					}
				}
				if (inside) {
					lo = Math.min(lo, line(loop));
					hi = Math.max(hi, loop.getEnd().map(p -> p.line).orElse(hi));
				}
			}
			m.loopExtent.put(v, new int[] { lo, hi });
		}
		return m;
	}

	/** The node a pattern variable is visible in: the switch entry, or the block of its statement. */
	static Node patternScope(Node pattern) {
		Node p = pattern.getParentNode().orElse(null);
		while (p != null) {
			if (p instanceof SwitchEntry) {
				return p;
			}
			if (p instanceof Statement) {
				return p.getParentNode().orElse(p);
			}
			p = p.getParentNode().orElse(null);
		}
		return pattern;
	}

	/** A simple name that is not a variable: a type or constant by convention, a case label, an annotation. */
	static boolean excluded(NameExpr ne) {
		if (UPPER.matcher(ne.getNameAsString()).matches()) {
			return true;
		}
		if (ne.findAncestor(AnnotationExpr.class).isPresent()) {
			return true;
		}
		return ne.getParentNode().orElse(null) instanceof SwitchEntry se && se.getLabels().contains(ne);
	}

	/** The innermost declaration of the name whose scope holds the use and that precedes it. */
	static Var resolve(NameExpr ne, List<Var> locals) {
		String s = ne.getNameAsString();
		int l = line(ne), c = col(ne);
		Var best = null;
		for (Var v : locals) {
			if (!v.name.equals(s) || !within(v.scope, ne)) {
				continue;
			}
			if (v.kind == LOCAL && (v.declLine > l || (v.declLine == l && v.declCol > c))) {
				continue;
			}
			if (best == null || within(best.scope, v.scope)) {
				best = v;
			}
		}
		return best;
	}

	/** The variable a write target rebinds: a simple name or {@code this.x}. */
	static Var varOf(Expression target, List<Var> locals, Map<String, Var> fields) {
		if (target instanceof NameExpr ne && !excluded(ne)) {
			Var v = resolve(ne, locals);
			return v != null ? v : fields.get(ne.getNameAsString());
		}
		if (target instanceof FieldAccessExpr fa && fa.getScope() instanceof ThisExpr) {
			return fields.get(fa.getNameAsString());
		}
		return null;
	}

	static boolean isLiteral(Expression e) {
		return e instanceof IntegerLiteralExpr || e instanceof LongLiteralExpr || e instanceof DoubleLiteralExpr
				|| e instanceof CharLiteralExpr;
	}

	// ------------------------------------------------------------------------------------------
	// output
	// ------------------------------------------------------------------------------------------

	/**
	 * Writes {"livewidth": SCHEMA, "javaparser", "seconds", "files": [{"path", "level", "problem",
	 * "methods": [{"name", "decl_line", "name_line", "end_line", "lines": [code lines], "loops":
	 * [[begin, end]], "vars": [[name, kind, first, last, loop_first, loop_last, defs, steps,
	 * muts]]}]}]}.
	 */
	static void write(Path out, List<FileFacts> recs, double seconds) throws IOException {
		Path tmp = out.resolveSibling(out.getFileName() + ".part");
		try (Writer w = new BufferedWriter(
				new OutputStreamWriter(new GZIPOutputStream(Files.newOutputStream(tmp)), StandardCharsets.UTF_8))) {
			w.write("{\"livewidth\":" + SCHEMA + ",\"javaparser\":");
			Measurer.str(w, Measurer.javaParserVersion());
			w.write(",\"seconds\":" + seconds + ",\"files\":[");
			for (int f = 0; f < recs.size(); f++) {
				FileFacts fr = recs.get(f);
				w.write(f > 0 ? ",\n" : "\n");
				w.write("{\"path\":");
				Measurer.str(w, fr.path);
				w.write(",\"level\":");
				Measurer.str(w, fr.level);
				w.write(",\"problem\":");
				Measurer.str(w, fr.problem);
				w.write(",\"methods\":[");
				for (int k = 0; k < fr.methods.size(); k++) {
					MethodFacts m = fr.methods.get(k);
					w.write(k > 0 ? "," : "");
					w.write("{\"name\":");
					Measurer.str(w, m.name);
					w.write(",\"decl_line\":" + m.declLine + ",\"name_line\":" + m.nameLine + ",\"end_line\":"
							+ m.endLine + ",\"lines\":[");
					int i = 0;
					for (int ln : m.lines) {
						w.write((i++ > 0 ? "," : "") + ln);
					}
					w.write("],\"loops\":[");
					for (int j = 0; j < m.loopRanges.size(); j++) {
						int[] r = m.loopRanges.get(j);
						w.write((j > 0 ? "," : "") + "[" + r[0] + "," + r[1] + "]");
					}
					w.write("],\"vars\":[");
					for (int j = 0; j < m.vars.size(); j++) {
						Var v = m.vars.get(j);
						int[] e = m.loopExtent.get(v);
						w.write(j > 0 ? ",[" : "[");
						Measurer.str(w, v.name);
						w.write("," + v.kind + "," + v.first + "," + v.last + "," + e[0] + "," + e[1] + "," + v.defs
								+ "," + v.steps + "," + v.muts + "]");
					}
					w.write("]}");
				}
				w.write("]}");
			}
			w.write("]}\n");
		}
		Files.move(tmp, out, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
	}
}
