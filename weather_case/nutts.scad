// latchalike?
$fn=100;
diameter = 3;

d2 = diameter - 0.5;
length = 5;

cylinder(h = length, d = diameter);
translate([0, 0, length])
{
cylinder(h = 2, d = d2);
  translate([0, 0, 2])
  cylinder(h = 2, d = diameter);
}

translate([0,0,1]) {
translate([12.3,0,0])
cube([2, 1, 2], center = true);
translate([10, 0, 0])
difference() {
  cylinder(h = 2, d = diameter+1, center = true);
  cylinder(h = 10, d = d2, center = true);
  translate([-3, 0, 0])
  cylinder(h = 10, d = diameter*2, center=true, $fn=1);
}
}