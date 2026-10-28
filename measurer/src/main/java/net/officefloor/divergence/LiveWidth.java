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
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
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
import com.github.javaparser.ast.expr.CastExpr;
import com.github.javaparser.ast.expr.CharLiteralExpr;
import com.github.javaparser.ast.expr.DoubleLiteralExpr;
import com.github.javaparser.ast.expr.EnclosedExpr;
import com.github.javaparser.ast.expr.Expression;
import com.github.javaparser.ast.expr.FieldAccessExpr;
import com.github.javaparser.ast.expr.InstanceOfExpr;
import com.github.javaparser.ast.expr.IntegerLiteralExpr;
import com.github.javaparser.ast.expr.LambdaExpr;
import com.github.javaparser.ast.expr.LiteralExpr;
import com.github.javaparser.ast.expr.LongLiteralExpr;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.expr.NameExpr;
import com.github.javaparser.ast.expr.ObjectCreationExpr;
import com.github.javaparser.ast.expr.SimpleName;
import com.github.javaparser.ast.expr.ThisExpr;
import com.github.javaparser.ast.expr.TypePatternExpr;
import com.github.javaparser.ast.expr.UnaryExpr;
import com.github.javaparser.ast.expr.VariableDeclarationExpr;
import com.github.javaparser.ast.stmt.BlockStmt;
import com.github.javaparser.ast.stmt.BreakStmt;
import com.github.javaparser.ast.stmt.CatchClause;
import com.github.javaparser.ast.stmt.ContinueStmt;
import com.github.javaparser.ast.stmt.DoStmt;
import com.github.javaparser.ast.stmt.ExplicitConstructorInvocationStmt;
import com.github.javaparser.ast.stmt.ForEachStmt;
import com.github.javaparser.ast.stmt.ForStmt;
import com.github.javaparser.ast.stmt.IfStmt;
import com.github.javaparser.ast.stmt.LabeledStmt;
import com.github.javaparser.ast.stmt.ReturnStmt;
import com.github.javaparser.ast.stmt.Statement;
import com.github.javaparser.ast.stmt.SwitchEntry;
import com.github.javaparser.ast.stmt.SwitchStmt;
import com.github.javaparser.ast.stmt.SynchronizedStmt;
import com.github.javaparser.ast.stmt.ThrowStmt;
import com.github.javaparser.ast.stmt.TryStmt;
import com.github.javaparser.ast.stmt.WhileStmt;
import com.github.javaparser.ast.stmt.YieldStmt;

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
 * parameter's declaration is not a reference (its signature line is written beside it).
 * <b>The literal rule:</b> a local declared with no initializer, or with a literal one
 * ({@code 0}, {@code -1}, {@code null}, {@code ""}, {@code false}, a cast or parenthesised
 * literal), depends on nothing above it, so the declaration could move down to the first use
 * without changing the method. Its declaration is not a use: {@code use_first} (and the loop
 * extent {@code use_loop_first}) start at the first use. {@code first} is as it always was (a
 * literal initializer is in the range, a declaration without a value is not a reference), so
 * the two readings can be compared. {@code lit} marks such a variable. The declaration still
 * counts as a definition when it has an initializer.</li>
 * <li><b>Reference lines</b> ({@code refs}): the distinct lines of the variable's uses, in
 * order, a literal declaration excluded. A reader can see from them where the variable is
 * touched, not only the range it is live over. <b>Definition lines</b> ({@code def_lines}):
 * the distinct lines of the definitions that have one (an initializer, a literal one included;
 * a for-each, catch, lambda or pattern binding; every assignment and increment); a parameter's
 * argument and a field's prior state have no line. <b>Write lines</b> ({@code mut_lines}): the
 * lines of the writes into the variable's object. So a reader can tell a read from a write at
 * any line, which the reference lines alone cannot.</li>
 * <li><b>Definitions</b> ({@code defs}): the value a variable enters with (a parameter's
 * argument, a field's prior state, a catch, lambda, for-each or pattern binding, an
 * initializer), plus every assignment and increment of the name. {@code steps}: the definitions
 * that are steps (an increment or decrement, {@code +=}/{@code -=} of a literal, or any
 * definition in a for statement's update). {@code muts}: writes into the variable's object
 * ({@code a[i] = v}, {@code a.f = v}), which do not rebind it.</li>
 * <li><b>Loops:</b> for each variable, the extent it is live over when control flow is followed
 * this far: a variable declared outside a loop and referenced inside it is live over the whole
 * loop (the back edge), so its range is widened to cover it.</li>
 * <li><b>Data flow</b> ({@code from}): the other variables any definition of a variable is
 * computed from (those referenced in an initializer, an assigned value, a for-each iterable, the
 * expression a pattern tests, or a value written into it), so a variable's value can be traced
 * back to what entered the method.</li>
 * <li><b>Calls:</b> every call the measurer counts (method calls, {@code new}, explicit
 * {@code this(...)}/{@code super(...)}), in the measurer's order, so the i-th call here is the
 * i-th call of the measurer's record and takes its resolution from there. Per call: its line, the
 * variables referenced in its arguments, the variable it is called on (a simple name or
 * {@code this.x} as the receiver), and the variable whose definition it is part of, if any
 * (the call's result flows into it).</li>
 * <li><b>Statement tree</b> ({@code tree}): the method body as nested ranges, so a reader can
 * tell where a cut may fall. Each node is {@code [first line, last line, seq, kind, children]}:
 * {@code seq} is 1 for a sequence (a block, a switch entry, a lambda's block body), whose
 * children are the statements in it in order, and 0 for a statement, whose children are the
 * sequences and statements directly inside it (an if's arms, a loop's body, a try's block and
 * catch bodies). {@code kind} names the statement: 0 any other (an expression, a declaration,
 * an assert), 1 return, 2 break, 3 continue, 4 throw, 5 yield, 6 if, 7 a loop (for, for-each,
 * while, do), 8 try, 9 switch, 10 synchronized, 11 labeled, 12 a block, 13 a switch entry. The
 * jumps (1 to 5) say whether a run can be moved; 6 to 9 are the structural cues developers cut
 * at. A contiguous run of a sequence's children is the unit Extract Method moves; nested type
 * bodies are not the method's own and are left out, as everywhere here.</li>
 * </ul>
 */
public final class LiveWidth {

	static final int PARAM = 0, LOCAL = 1, FIELD = 2;

	/** The facts schema, bumped with any change to the rules above. */
	static final int SCHEMA = 3;

	static final Pattern UPPER = Pattern.compile("^[A-Z].*");

	static final class Var {
		final int kind;
		final String name;
		/** The node the declaration is visible in (null for a field; released once measured). */
		Node scope;
		/** Where the declaration is, for the declared-before rule (0 for a parameter or field). */
		final int declLine, declCol;
		final List<Node> refs = new ArrayList<>();
		/** The distinct lines of the uses (a literal declaration is not one). */
		final TreeSet<Integer> refLines = new TreeSet<>();
		/** The distinct lines of the definitions that have a line, and of the writes into it. */
		final TreeSet<Integer> defLines = new TreeSet<>(), mutLines = new TreeSet<>();
		/** The variables its definitions are computed from (identity, in order met). */
		final Set<Var> from = new LinkedHashSet<>();
		int first = Integer.MAX_VALUE, last = -1, defs, steps, muts;
		/** Declared with no initializer or a literal one: the range may start at the first use. */
		boolean literal;

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
			refLines.add(line);
			first = Math.min(first, line);
			last = Math.max(last, line);
		}

		/** A literal initializer: the declaration is in the range (as any initializer was), not a use. */
		void declare(int line) {
			literal = true;
			first = Math.min(first, line);
			last = Math.max(last, line);
		}

		/** The first use, or the declaration when there is none. */
		int useFirst() {
			return refLines.isEmpty() ? first : refLines.first();
		}

		/**
		 * Drop the parse-tree nodes once the method's facts are computed: a node reaches its
		 * whole compilation unit through its parent, and the facts of every file are held until
		 * they are written, so keeping them kept every file's tree alive (heap exhausted on a
		 * repository of 15,000+ files).
		 */
		void release() {
			refs.clear();
			scope = null;
		}
	}

	static final class MethodFacts {
		String name;
		int declLine, nameLine, endLine;
		final TreeSet<Integer> lines = new TreeSet<>();
		final List<Var> vars = new ArrayList<>();
		final List<int[]> loopRanges = new ArrayList<>();
		final Map<Var, int[]> loopExtent = new IdentityHashMap<>();
		final List<CallFacts> calls = new ArrayList<>();
		Stmt tree;
	}

	static final class CallFacts {
		int line;
		Set<Var> args = new LinkedHashSet<>(), receiver = new LinkedHashSet<>();
		Var result;
	}

	/** A node of the statement tree: a sequence (block, switch entry) or a statement. */
	static final class Stmt {
		int start, end, kind;
		boolean seq;
		final List<Stmt> kids = new ArrayList<>();
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
		for (MethodFacts m : rec.methods) {
			for (Var v : m.vars) {
				v.release();
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
		m.tree = tree(body);
		m.lines.add(m.nameLine);
		for (Node n : own) {
			m.lines.add(line(n));
		}

		// declarations, each with the node it is visible in
		List<Var> locals = new ArrayList<>();
		Map<Node, Var> declared = new IdentityHashMap<>();
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
					v.defLines.add(line(vd.getName()));
				}
				if (holder instanceof ForEachStmt || (bound && !literal(vd.getInitializer().get()))) {
					v.ref(vd.getName());
				} else if (bound) {
					v.declare(line(vd.getName())); // a literal: in the range, not a use
				} else {
					v.literal = true; // no value: not a reference at all, so the range starts at the first use
				}
				locals.add(v);
				declared.put(vd, v);
			} else if (n instanceof Parameter p) {
				Node owner = p.getParentNode().orElse(null);
				if (owner instanceof CatchClause || owner instanceof LambdaExpr) {
					Var v = new Var(LOCAL, p.getNameAsString(), owner, p.getName(), 1);
					v.defLines.add(line(p.getName()));
					locals.add(v);
				}
			} else if (n instanceof TypePatternExpr tp) {
				Var v = new Var(LOCAL, tp.getNameAsString(), patternScope(tp), tp.getName(), 1);
				v.defLines.add(line(tp.getName()));
				v.ref(tp.getName());
				locals.add(v);
				declared.put(tp, v);
			}
		}

		// references, matched to the innermost declaration in scope
		Map<String, Var> fields = new LinkedHashMap<>();
		Map<Node, Var> refOf = new IdentityHashMap<>();
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
				refOf.put(ne, v);
			} else if (n instanceof FieldAccessExpr fa && fa.getScope() instanceof ThisExpr) {
				v = fields.computeIfAbsent(fa.getNameAsString(), k -> new Var(FIELD, k, null, null, 1));
				v.ref(fa);
				refOf.put(fa, v);
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
			Expression value = n instanceof AssignExpr ae ? ae.getValue() : null;
			Var rebound = varOf(target, locals, fields);
			if (rebound != null) {
				if (value != null) {
					flowInto(rebound, value, refOf);
				}
				rebound.defs++;
				rebound.defLines.add(line(n));
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
					into.mutLines.add(line(n));
					if (value != null) {
						flowInto(into, value, refOf);
					}
					break;
				}
			}
		}

		// what the bindings are computed from
		for (Map.Entry<Node, Var> e : declared.entrySet()) {
			Node d = e.getKey();
			if (d instanceof VariableDeclarator vd) {
				vd.getInitializer().ifPresent(init -> flowInto(e.getValue(), init, refOf));
				if (vd.getParentNode().flatMap(Node::getParentNode).orElse(null) instanceof ForEachStmt fe) {
					flowInto(e.getValue(), fe.getIterable(), refOf);
				}
			} else if (d.getParentNode().orElse(null) instanceof InstanceOfExpr io) {
				flowInto(e.getValue(), io.getExpression(), refOf);
			}
		}

		// the calls, in the measurer's order
		for (Node n : own) {
			NodeList<Expression> args;
			Expression scope = null;
			if (n instanceof MethodCallExpr mce) {
				args = mce.getArguments();
				scope = mce.getScope().orElse(null);
			} else if (n instanceof ObjectCreationExpr oce) {
				args = oce.getArguments();
			} else if (n instanceof ExplicitConstructorInvocationStmt ecis) {
				args = ecis.getArguments();
			} else {
				continue;
			}
			CallFacts c = new CallFacts();
			c.line = line(n);
			for (Expression a : args) {
				collect(a, refOf, c.args);
			}
			if (scope != null && refOf.containsKey(scope)) {
				c.receiver.add(refOf.get(scope));
			}
			c.result = resultOf(n, declared, locals, fields);
			m.calls.add(c);
		}

		for (Var v : locals) {
			if (v.last >= 0) { // referenced, or declared with a literal
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
			int lo = v.first, hi = v.last, useLo = v.useFirst();
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
					useLo = Math.min(useLo, line(loop));
					hi = Math.max(hi, loop.getEnd().map(p -> p.line).orElse(hi));
				}
			}
			m.loopExtent.put(v, new int[] { lo, hi, useLo });
		}
		return m;
	}

	/** The statement tree under a node: its statements and switch entries, nested types left out. */
	static Stmt tree(Node n) {
		Stmt s = new Stmt();
		s.start = line(n);
		s.end = n.getEnd().map(p -> p.line).orElse(s.start);
		s.seq = n instanceof BlockStmt || n instanceof SwitchEntry;
		s.kind = kind(n);
		kids(n, s.kids);
		return s;
	}

	static int kind(Node n) {
		if (n instanceof ReturnStmt) {
			return 1;
		} else if (n instanceof BreakStmt) {
			return 2;
		} else if (n instanceof ContinueStmt) {
			return 3;
		} else if (n instanceof ThrowStmt) {
			return 4;
		} else if (n instanceof YieldStmt) {
			return 5;
		} else if (n instanceof IfStmt) {
			return 6;
		} else if (n instanceof ForStmt || n instanceof ForEachStmt || n instanceof WhileStmt || n instanceof DoStmt) {
			return 7;
		} else if (n instanceof TryStmt) {
			return 8;
		} else if (n instanceof SwitchStmt) {
			return 9;
		} else if (n instanceof SynchronizedStmt) {
			return 10;
		} else if (n instanceof LabeledStmt) {
			return 11;
		} else if (n instanceof BlockStmt) {
			return 12;
		} else if (n instanceof SwitchEntry) {
			return 13;
		}
		return 0;
	}

	static void kids(Node n, List<Stmt> out) {
		for (Node c : n.getChildNodes()) {
			if (Measurer.isNestedTypePart(n, c)) {
				continue;
			}
			if (c instanceof Statement || c instanceof SwitchEntry) {
				out.add(tree(c));
			} else {
				kids(c, out);
			}
		}
	}

	static void writeTree(Writer w, Stmt s) throws IOException {
		w.write("[" + s.start + "," + s.end + "," + (s.seq ? 1 : 0) + "," + s.kind + ",[");
		for (int i = 0; i < s.kids.size(); i++) {
			w.write(i > 0 ? "," : "");
			writeTree(w, s.kids.get(i));
		}
		w.write("]]");
	}

	/** A literal, or one under a unary sign, a cast or parentheses: a value from nowhere. */
	static boolean literal(Expression e) {
		if (e instanceof LiteralExpr) {
			return true;
		}
		if (e instanceof UnaryExpr u) {
			return literal(u.getExpression());
		}
		if (e instanceof CastExpr c) {
			return literal(c.getExpression());
		}
		if (e instanceof EnclosedExpr p) {
			return literal(p.getInner());
		}
		return false;
	}

	/** The variables referenced in an expression (nested type bodies excluded). */
	static void collect(Node n, Map<Node, Var> refOf, Set<Var> out) {
		Var v = refOf.get(n);
		if (v != null) {
			out.add(v);
		}
		for (Node c : n.getChildNodes()) {
			if (!Measurer.isNestedTypePart(n, c)) {
				collect(c, refOf, out);
			}
		}
	}

	/** The variables an expression references flow into {@code into} (itself excluded). */
	static void flowInto(Var into, Expression value, Map<Node, Var> refOf) {
		Set<Var> vs = new LinkedHashSet<>();
		collect(value, refOf, vs);
		vs.remove(into);
		into.from.addAll(vs);
	}

	/**
	 * The variable a call's result flows into: the declarator whose initializer, or the
	 * assignment whose value, holds the call, up to the call's statement or lambda.
	 */
	static Var resultOf(Node call, Map<Node, Var> declared, List<Var> locals, Map<String, Var> fields) {
		Node child = call;
		Node p = call.getParentNode().orElse(null);
		while (p != null && !(p instanceof Statement) && !(p instanceof LambdaExpr)) {
			if (p instanceof VariableDeclarator vd && vd.getInitializer().orElse(null) == child) {
				return declared.get(vd);
			}
			if (p instanceof AssignExpr ae && ae.getValue() == child) {
				return varOf(ae.getTarget(), locals, fields);
			}
			child = p;
			p = p.getParentNode().orElse(null);
		}
		return null;
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
	 * muts, [from: variable indices]]], "calls": [[line, [argument variable indices], [receiver
	 * variable indices], result variable index or -1]]}]}]}.
	 */
	static String ints(Iterable<Integer> xs) {
		StringBuilder b = new StringBuilder("[");
		for (int x : xs) {
			b.append(b.length() > 1 ? "," : "").append(x);
		}
		return b.append(']').toString();
	}

	static String indices(Set<Var> vs, Map<Var, Integer> index) {
		StringBuilder b = new StringBuilder("[");
		for (Var v : vs) {
			Integer i = index.get(v);
			if (i != null) {
				b.append(b.length() > 1 ? "," : "").append(i);
			}
		}
		return b.append(']').toString();
	}

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
					Map<Var, Integer> index = new IdentityHashMap<>();
					for (int j = 0; j < m.vars.size(); j++) {
						index.put(m.vars.get(j), j);
					}
					for (int j = 0; j < m.vars.size(); j++) {
						Var v = m.vars.get(j);
						int[] e = m.loopExtent.get(v);
						w.write(j > 0 ? ",[" : "[");
						Measurer.str(w, v.name);
						w.write("," + v.kind + "," + v.first + "," + v.last + "," + e[0] + "," + e[1] + "," + v.defs
								+ "," + v.steps + "," + v.muts + "," + indices(v.from, index) + "," + (v.literal ? 1 : 0)
								+ "," + v.useFirst() + "," + e[2] + "," + ints(v.refLines) + "," + ints(v.defLines) + ","
								+ ints(v.mutLines) + "]");
					}
					w.write("],\"calls\":[");
					for (int j = 0; j < m.calls.size(); j++) {
						CallFacts c = m.calls.get(j);
						Integer r = c.result == null ? null : index.get(c.result);
						w.write((j > 0 ? ",[" : "[") + c.line + "," + indices(c.args, index) + ","
								+ indices(c.receiver, index) + "," + (r == null ? -1 : r) + "]");
					}
					w.write("],\"tree\":");
					writeTree(w, m.tree);
					w.write("}");
				}
				w.write("]}");
			}
			w.write("]}\n");
		}
		Files.move(tmp, out, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
	}
}
